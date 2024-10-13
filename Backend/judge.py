import re
import requests

def extract_relevant_lines(transcript):
    """
    Extract lines from the transcript based on the criteria:
    - Lines with a question mark (?) and the one immediately after.
    - Lines with 'Objection' and the one immediately after.
    - The last line of the transcript if it contains 'Objection' and the type of objection.
    """
    lines = transcript.splitlines()
    relevant_lines = []
    objection_type = None

    for i, line in enumerate(lines):
        if '?' in line:
            relevant_lines.append(line)
            if i + 1 < len(lines):
                relevant_lines.append(lines[i + 1])

        if 'Objection' in line:
            relevant_lines.append(line)
            if i + 1 < len(lines):
                relevant_lines.append(lines[i + 1])

            # Check if the line contains a specific objection type
            objection_match = re.search(r'Objection.*?\b(Hearsay|Relevance|Leading the Witness|Speculation|Lack of Foundation|Opinion Testimony by Lay Witness|Improper Expert Opinion|Argumentative|Asked and Answered|Vague|Compound Question|Misleading|Privileged Communication|Improper Character Evidence|Prejudicial|Improper Impeachment|Best Evidence Rule|Non-responsive|Improper Closing Argument)\b', line, re.IGNORECASE)
            if objection_match:
                objection_type = objection_match.group(1)

    # Check if the last line has 'Objection' and an objection type
    last_line = lines[-1]
    if 'Objection' in last_line:
        relevant_lines.append(last_line)
        last_objection_match = re.search(r'Objection.*?\b(Hearsay|Relevance|Leading the Witness|Speculation|Lack of Foundation|Opinion Testimony by Lay Witness|Improper Expert Opinion|Argumentative|Asked and Answered|Vague|Compound Question|Misleading|Privileged Communication|Improper Character Evidence|Prejudicial|Improper Impeachment|Best Evidence Rule|Non-responsive|Improper Closing Argument)\b', last_line, re.IGNORECASE)
        if last_objection_match:
            objection_type = last_objection_match.group(1)

    return relevant_lines, objection_type


def get_objection_prompt(objection_type):
    """
    Based on the objection type, select the corresponding prompt.
    """
    objection_prompts = {
        "Hearsay": "Can the last objection really be sustained as Hearsay?",
        "Relevance": "Can the last objection really be sustained as Relevance?",
        "Leading the Witness": "Can the last objection really be sustained as Leading the Witness?",
        "Speculation": "Can the last objection really be sustained as Speculation?",
        "Lack of Foundation": "Can the last objection really be sustained as Lack of Foundation?",
        "Opinion Testimony by Lay Witness": "Can the last objection really be sustained as Opinion Testimony by Lay Witness?",
        "Improper Expert Opinion": "Can the last objection really be sustained as Improper Expert Opinion?",
        "Argumentative": "Can the last objection really be sustained as Argumentative?",
        "Asked and Answered": "Can the last objection really be sustained as Asked and Answered?",
        "Vague": "Can the last objection really be sustained as Vague?",
        "Compound Question": "Can the last objection really be sustained as Compound Question?",
        "Misleading": "Can the last objection really be sustained as Misleading?",
        "Privileged Communication": "Can the last objection really be sustained as Privileged Communication?",
        "Improper Character Evidence": "Can the last objection really be sustained as Improper Character Evidence?",
        "Prejudicial": "Can the last objection really be sustained as Prejudicial?",
        "Improper Impeachment": "Can the last objection really be sustained as Improper Impeachment?",
        "Best Evidence Rule": "Can the last objection really be sustained as Best Evidence Rule?",
        "Non-responsive": "Can the last objection really be sustained as Non-responsive?",
        "Improper Closing Argument": "Can the last objection really be sustained as Improper Closing Argument?"
    }

    return objection_prompts.get(objection_type, "Unknown objection type")


def generate_judge_prompt(objection_type, relevant_lines):
    """
    Create a final prompt to guide the AI into the role of a judge,
    instructing it to reason and respond only with 1 for sustained and 0 for overruled.
    """
    base_prompt = """
    You are acting as a judge in a court of law. Carefully review the last objection in the case,
    consider the type of objection made, and determine if it should be sustained or overruled.
    Base your judgment on solid legal reasoning and the rules of evidence.
    Your response must be clear and accurate, and you should only respond with a '1' if the objection should be sustained
    and a '0' if the objection should be overruled. Do not include any additional text, explanations,
    or comments—only respond with '1' or '0'.
    Here are the relevant lines from the transcript:
    """
    relevant_lines_str = "\n".join(relevant_lines)
    specific_objection_prompt = get_objection_prompt(objection_type)

    return base_prompt + relevant_lines_str + "\n" + specific_objection_prompt


def call_perplexity_api(prompt):
    """
    Call the Perplexity API with the provided prompt and return the response.
    """
    api_key = "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"
    api_url = "https://api.perplexity.ai/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        result = response.json()
        # Post-process the response to ensure only '1' or '0' is returned
        answer = result['choices'][0]['message']['content'].strip()

        try:
            # Cast to boolean: '1' -> True, '0' -> False
            boolean_result = bool(int(answer))
            return boolean_result
        except ValueError:
            return "Error: Response was not '1' or '0'"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    else:
        return f"Error: {response.status_code} - {response.text}"


def generate_perplexity_api_payload(transcript):
    """
    Generate the API payload for Perplexity AI based on the extracted objection.
    """
    relevant_lines, objection_type = extract_relevant_lines(transcript)

    if objection_type:
        judge_prompt = generate_judge_prompt(objection_type, relevant_lines)
    else:
        judge_prompt = "No valid objection found in the transcript."

    return call_perplexity_api(judge_prompt)


# Example usage
transcript = """
Lawyer: Where were you on the night of the incident?
Witness: I was at home.
Lawyer: Did you hear anything strange?
Witness: Yes, I heard a loud noise.
Objection, Hearsay!
"""

#result = generate_perplexity_api_payload(transcript)
#print(result)
