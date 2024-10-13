# trial_state_machine.py

from models import db_session, User, Trial, TranscriptEntry, Evidence, Witness, JuryMember, UserRole, TrialPhase
from flask_socketio import emit
from uuid import uuid4
from datetime import datetime
from random import choice as rand_choice
from jury_generation import addBackgroundToFacts
from judge import generate_perplexity_api_payload
from concurrent.futures import ThreadPoolExecutor

class TrialStateMachine:
    def __init__(self, trial, socketio):
        self.trial = trial
        self.room = f"trial_{self.trial.trial_id}"
        self.participants_ready = {self.trial.plaintiff_id: False, self.trial.defendant_id: False}
        self.socketio = socketio

    def advance_phase(self, next_phase):
        self.trial.current_phase = next_phase
        db_session.commit()
        # Notify all clients in the room
        self.socketio.emit('phase_advanced', {'next_phase': next_phase.value}, room=self.room)

    def set_turn(self, username):
        self.trial.current_turn_username = username
        db_session.commit()
        # Notify clients
        self.socketio.emit('turn_changed', {'current_turn': username}, room=self.room)

    def get_current_user(self):
        return db_session.query(User).filter_by(username=self.trial.current_turn_username).first()

    def get_role(self, username):
        if self.trial.plaintiff_id == username:
            return UserRole.plaintiff.value
        elif self.trial.defendant_id == username:
            return UserRole.defendant.value
        else:
            return None

    def switch_turn(self):
        next_user = self.trial.defendant_id if self.trial.current_turn_username == self.trial.plaintiff_id else self.trial.plaintiff_id
        self.set_turn(next_user)

    def add_evidence(self, username, description):
        evidence = Evidence(
            evidence_id=str(uuid4()),
            trial_id=self.trial.trial_id,
            submitted_by_username=username,
            description=description,
            used=False
        )
        db_session.add(evidence)
        db_session.commit()
        # Notify clients
        self.socketio.emit('evidence_updated', {'username': username, 'description': description}, room=self.room)

    def add_witness(self, username, witness_name):
        witness = Witness(
            witness_id=str(uuid4()),
            name=witness_name,
            trial_id=self.trial.trial_id,
            called_by_username=username
        )
        db_session.add(witness)
        db_session.commit()
        # Notify clients
        self.socketio.emit('witness_updated', {'username': username, 'witness_name': witness_name}, room=self.room)

    def generate_jury(self):
        def generate_single_jury_member():
            # Call the method to generate background and details for a jury member
            jury_data = addBackgroundToFacts()

            # Parse the returned data (assuming the format is fixed as in the example)
            lines = jury_data.split("\n")
            name = lines[0].split(": ")[1].strip()
            gender = lines[1].split(": ")[1].strip()
            race = lines[2].split(": ")[1].strip()
            birth_country = lines[3].split(": ")[1].strip()
            schools = lines[4].split(": ")[1].strip().split(", ")
            political_affiliations = lines[5].split(": ")[1].strip()

            # Create the JuryMember object with the parsed data
            jury_member = JuryMember(
                jury_member_id=str(uuid4()),
                trial_id=self.trial.trial_id,
                name=name,
                gender=gender,
                race=race,
                birth_country=birth_country,
                schools=schools,
                political_affiliations=political_affiliations
            )

            # Return the jury member object for later addition to the database
            return jury_member


        # Create a ThreadPoolExecutor to manage parallel tasks
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit 5 tasks to generate jury members in parallel
            futures = [executor.submit(generate_single_jury_member) for _ in range(5)]

            # Collect the results (jury members)
            jury_members = [future.result() for future in futures]

        # Add the generated jury members to the database
        db_session.add_all(jury_members)
        db_session.commit()

        # Notify clients (optional)
        self.socketio.emit('jury_generated', {'message': 'Jury members have been generated and added to the trial.'}, room=self.room)


    def save_transcript_entry(self, speaker_username, speaker_role, content, action_type):
        entry = TranscriptEntry(
            entry_id=str(uuid4()),
            trial_id=self.trial.trial_id,
            timestamp=datetime.now(),
            speaker_username=speaker_username,
            speaker_role=speaker_role,
            content=content,
            action_type=action_type
        )
        db_session.add(entry)
        db_session.commit()
        # Notify clients
        self.socketio.emit('transcript_updated', {
            'timestamp': entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            'speaker_role': speaker_role,
            'speaker_username': speaker_username,
            'content': content,
            'action_type': action_type
        }, room=self.room)

    def check_all_ready(self):
        if all(self.participants_ready.values()):
            # Advance to Opening Statements
            self.advance_phase(TrialPhase.opening_statements)
            # Reset readiness
            self.participants_ready = {k: False for k in self.participants_ready}
            # Set turn to plaintiff
            self.set_turn(self.trial.plaintiff_id)

    def judge_rule_objection(self):
        # Fetch all TranscriptEntry objects for the current trial
        transcript_entries = db_session.query(TranscriptEntry).filter_by(trial_id=self.trial.trial_id).all()

        # Convert the transcript entries into a string
        transcript_string = "\n".join([f"{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - "
                                       f"{entry.speaker_role} ({entry.speaker_username}): {entry.content}"
                                       for entry in transcript_entries])

        # Use the transcript string to get a result (True/False)
        result = generate_perplexity_api_payload(transcript_string)

        # Judge makes a ruling based on the result
        if result:
            ruling = "sustained"
        else:
            ruling = "overruled"

        # Save the ruling to the transcript
        self.save_transcript_entry(None, 'judge', f"Objection {ruling}.", 'judge_ruling')

        return ruling



    def process_verdict(self):
        verdict = rand_choice(['in_favor_of_plaintiff', 'in_favor_of_defendant'])
        reasoning = "Based on the evidence and testimony presented."
        self.save_transcript_entry(None, 'jury', f"Verdict: {verdict}. Reasoning: {reasoning}", 'verdict')
        self.socketio.emit('verdict_announced', {'verdict': verdict, 'reasoning': reasoning}, room=self.room)
