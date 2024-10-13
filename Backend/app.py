
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from models import db_session, User, Trial, TranscriptEntry, Evidence, Witness, JuryMember, UserRole, TrialPhase
from trial_state_machine import TrialStateMachine
from uuid import uuid4
from datetime import datetime


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, async_mode='eventlet')

# Dictionary to hold trial state machines
trial_state_machines = {}

# REST endpoint to create a new trial
@app.route('/create_trial', methods=['POST'])
def create_trial():
    data = request.get_json()
    username1 = data.get('username1')
    username2 = data.get('username2')
    description = data.get('description')

    if not username1 or not username2 or not description:
        return jsonify({'error': 'Missing required fields'}), 400

    # Create users if they don't exist
    user1 = db_session.query(User).filter_by(username=username1).first()
    if not user1:
        user1 = User(username=username1)
        db_session.add(user1)

    user2 = db_session.query(User).filter_by(username=username2).first()
    if not user2:
        user2 = User(username=username2)
        db_session.add(user2)

    db_session.commit()

    # Create trial
    trial_id = str(uuid4())
    trial_title = f"{username1} v. {username2}"
    trial = Trial(
        trial_id=trial_id,
        title=trial_title,
        description=description,
        plaintiff_id=username1,
        defendant_id=username2,
        current_phase=TrialPhase.pre_trial,
        created_at=datetime.now()
    )
    db_session.add(trial)
    db_session.commit()

    return jsonify({'trial_id': trial_id})

# Endpoint to fetch case library (evidence and witnesses)
@app.route('/case_library/<trial_id>', methods=['GET'])
def get_case_library(trial_id):
    evidence_list = db_session.query(Evidence).filter_by(trial_id=trial_id).all()
    witnesses_list = db_session.query(Witness).filter_by(trial_id=trial_id).all()

    evidence = [{'description': e.description, 'submitted_by': e.submitted_by_username} for e in evidence_list]
    witnesses = [{'name': w.name, 'called_by': w.called_by_username} for w in witnesses_list]

    return jsonify({'evidence': evidence, 'witnesses': witnesses})

# Endpoint to check if opponent is ready
@app.route('/opponent_ready/<trial_id>/<username>', methods=['GET'])
def opponent_ready(trial_id, username):
    state_machine = trial_state_machines.get(trial_id)
    if not state_machine:
        return jsonify({'error': 'Trial not found'}), 404

    opponents = [user for user in state_machine.participants_ready if user != username]
    if not opponents:
        return jsonify({'error': 'Opponent not found'}), 404

    opponent_username = opponents[0]
    is_ready = state_machine.participants_ready[opponent_username]

    return jsonify({'opponent_ready': is_ready})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/trial')
def trial_page():
    return render_template('trial.html')

@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join_trial')
def on_join_trial(data):
    username = data['username']
    trial_id = data['trial_id']
    user = db_session.query(User).filter_by(username=username).first()
    trial = db_session.query(Trial).filter_by(trial_id=trial_id).first()

    if not user or not trial:
        emit('error', {'message': 'Invalid user or trial.'})
        return

    # Join the trial room
    join_room(f"trial_{trial_id}")
    emit('joined_trial', {'message': f"{username} has joined the trial."}, room=f"trial_{trial_id}")

    # Initialize trial state machine if not already done
    if trial_id not in trial_state_machines:
        trial_state_machines[trial_id] = TrialStateMachine(trial, socketio)

    # Send the current state to the client
    state_machine = trial_state_machines[trial_id]
    emit('trial_state', {
        'current_phase': state_machine.trial.current_phase.value,
        'current_turn': state_machine.trial.current_turn_username
    })

@socketio.on('submit_evidence')
def on_submit_evidence(data):
    username = data['username']
    trial_id = data['trial_id']
    description = data['description']
    state_machine = trial_state_machines.get(trial_id)
    if state_machine:
        state_machine.add_evidence(username, description)
    else:
        emit('error', {'message': 'Trial not found.'})

@socketio.on('submit_witness')
def on_submit_witness(data):
    username = data['username']
    trial_id = data['trial_id']
    witness_name = data['witness_name']
    state_machine = trial_state_machines.get(trial_id)
    if state_machine:
        state_machine.add_witness(username, witness_name)
    else:
        emit('error', {'message': 'Trial not found.'})

@socketio.on('ready_for_next_phase')
def on_ready_for_next_phase(data):
    username = data['username']
    trial_id = data['trial_id']
    state_machine = trial_state_machines.get(trial_id)
    if state_machine:
        state_machine.participants_ready[username] = True
        emit('user_ready', {'username': username}, room=state_machine.room)
        # Check if both parties are ready
        state_machine.check_all_ready()
    else:
        emit('error', {'message': 'Trial not found.'})

@socketio.on('submit_action')
def on_submit_action(data):
    username = data['username']
    trial_id = data['trial_id']
    action_type = data['action_type']
    content = data.get('content', '')
    state_machine = trial_state_machines.get(trial_id)

    if not state_machine:
        emit('error', {'message': 'Trial not found.'})
        return

    if state_machine.trial.current_turn_username != username:
        emit('error', {'message': 'Not your turn.'})
        return

    role = state_machine.get_role(username)

    # Process the action
    if action_type == 'opening_statement':
        state_machine.save_transcript_entry(username, role, content, 'opening_statement')
        # Switch to next user or phase
        if state_machine.trial.current_turn_username == state_machine.trial.defendant_id:
            # Advance to Plaintiff's Presentation of Evidence
            state_machine.advance_phase(TrialPhase.presentation_of_evidence_plaintiff)
            state_machine.set_turn(state_machine.trial.plaintiff_id)
        else:
            state_machine.switch_turn()
    elif action_type == 'call_witness':
        witness_name = data.get('witness_name')
        state_machine.save_transcript_entry(username, role, f"Called witness: {witness_name}", 'call_witness')
        # Notify clients to start examination phase
        socketio.emit('start_examination', {'witness_name': witness_name}, room=state_machine.room)
    elif action_type == 'introduce_evidence':
        evidence_description = data.get('evidence_description')
        state_machine.save_transcript_entry(username, role, f"Introduced evidence: {evidence_description}", 'introduce_evidence')
    elif action_type == 'rest_case':
        state_machine.save_transcript_entry(username, role, f"{username} rests their case.", 'rest_case')
        # Advance phase or switch turn
        if state_machine.trial.current_phase == TrialPhase.presentation_of_evidence_plaintiff:
            state_machine.advance_phase(TrialPhase.presentation_of_evidence_defendant)
            state_machine.set_turn(state_machine.trial.defendant_id)
        elif state_machine.trial.current_phase == TrialPhase.presentation_of_evidence_defendant:
            state_machine.advance_phase(TrialPhase.rebuttal)
            state_machine.set_turn(state_machine.trial.plaintiff_id)
        elif state_machine.trial.current_phase == TrialPhase.rebuttal:
            state_machine.advance_phase(TrialPhase.closing_arguments)
            state_machine.set_turn(state_machine.trial.plaintiff_id)
    elif action_type == 'closing_argument':
        state_machine.save_transcript_entry(username, role, content, 'closing_argument')
        # Switch to next user or advance to verdict
        if state_machine.trial.current_turn_username == state_machine.trial.defendant_id:
            # Proceed to verdict
            state_machine.advance_phase(TrialPhase.verdict)
            state_machine.process_verdict()
        else:
            state_machine.switch_turn()
    else:
        # Handle other actions
        pass

@socketio.on('submit_question')
def on_submit_question(data):
    username = data['username']
    trial_id = data['trial_id']
    question = data['question']
    state_machine = trial_state_machines.get(trial_id)
    role = state_machine.get_role(username)
    state_machine.save_transcript_entry(username, role, f"Q: {question}", 'question')
    # Notify opponent for possible objection
    socketio.emit('question_asked', {'question': question, 'asked_by': username}, room=state_machine.room)

@socketio.on('object')
def on_object(data):
    username = data['username']
    trial_id = data['trial_id']
    reason = data['reason']
    state_machine = trial_state_machines.get(trial_id)
    role = state_machine.get_role(username)
    state_machine.save_transcript_entry(username, role, f"Objection: {reason}", 'objection')
    # Handle judge ruling
    ruling = state_machine.judge_rule_objection()
    emit('objection_ruled', {'ruling': ruling}, room=state_machine.room)

@socketio.on('disconnect')
def on_disconnect():
    print(f"Client disconnected: {request.sid}")

if __name__ == "__main__":
    # No need to create trial here anymore
    socketio.run(app, debug=True, host="0.0.0.0", port=80)
