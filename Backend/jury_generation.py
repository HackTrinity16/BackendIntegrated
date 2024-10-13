import requests
import random
import json

def getRealFacts():
    # Step 1: Fetch political affiliations data
    response = requests.get("https://www.courtlistener.com/api/rest/v4/political-affiliations/")
    data = response.json()

    # Step 2: Randomly select one political affiliation
    results = data.get("results", [])

    random_affiliation = random.choice(results)
    person_id = random_affiliation["person"].split("/")[-2]

    # Step 3: Fetch person details using their ID
    person_url = f"https://www.courtlistener.com/api/rest/v4/people/{person_id}/"
    person_response = requests.get(person_url)
    person_data = person_response.json()

    # Step 4: Extract essential information
    essential_info = {
        "full_name": f"{person_data.get('name_first', '')} {person_data.get('name_middle', '')} {person_data.get('name_last', '')}".strip(),
        "gender": person_data.get("gender"),
        "race": person_data.get("race", []),
        "dob_country": person_data.get("dob_country"),
        "schools": [school['school']['name'] for school in person_data.get("educations", [])],
        "political_affiliations": [{
            "party": aff.get("political_party"),
        } for aff in person_data.get("political_affiliations", [])]
    }

    return essential_info


def generateMadeUpBackground(essential_info):
    prompt = f"""
    Imagine you are generating a fictional background for a member of a legal jury in a trial. You already have information like their full name, race, gender, and birth city, but we don't need education history, political affiliations, or any known facts.

    Please create extra background details including:
    - Work experience in non-legal fields
    - Personal hobbies and interests
    - Family background and upbringing
    - Personality traits and quirks
    - Places they've traveled to or lived

    Provide this in a believable and interesting manner. There should be tags that clearly indicate the detail you're referring to and do not add anything else in your response except for these details.
    The tag is only ###, and ** for subpoints. do not invent or use any other notation.

    Here is what we know:
    - Full Name: {essential_info.get('full_name')}
    - Gender: {essential_info.get('gender')}
    - Race: {', '.join(essential_info.get('race', []))}
    - Birth Country: {essential_info.get('dob_country')}
    - Schools: {', '.join(essential_info.get('schools', []))}
    - Political Affiliation: {', '.join([aff['party'] for aff in essential_info.get('political_affiliations', [])])}

    Please expand with extra information. Do not provide an end explanation.
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
        return result['choices'][0]['message']['content']
    else:
        return f"Error: {response.status_code} - {response.text}"

def parseGeneratedBackground(raw_background):
    parsed_background = {}
    current_tag = None
    current_subpoint = None

    for line in raw_background.splitlines():
        line = line.strip()

        if line.startswith("###"):
            # New tag
            current_tag = line[4:].strip()
            parsed_background[current_tag] = []
            current_subpoint = None  # Reset subpoint

        elif line.startswith("- **"):
            # New subpoint with **
            subpoint = line[4:].split("**", 1)
            if len(subpoint) == 2:
                key, value = subpoint
                current_subpoint = {key.strip(): value.strip()}
                parsed_background[current_tag].append(current_subpoint)

        elif current_subpoint is not None:
            # Continuation of the previous subpoint
            for key in current_subpoint:
                current_subpoint[key] += f" {line}"

    return parsed_background


def convert_to_text(essential_info):
    text_output = ""
    # Convert real facts
    text_output += f"Full Name: {essential_info['full_name']}\n"
    text_output += f"Gender: {essential_info['gender']}\n"
    text_output += f"Race: {', '.join(essential_info['race'])}\n"
    text_output += f"Birth Country: {essential_info['dob_country']}\n"
    text_output += f"Schools: {', '.join(essential_info['schools'])}\n"
    text_output += f"Political Affiliations: {', '.join([aff['party'] for aff in essential_info['political_affiliations']])}\n"

    # Convert made-up background
    text_output += "\nMade-up Background:\n"
    made_up_background = essential_info.get("made_up_background", {})
    for section, details in made_up_background.items():
        text_output += f"\n### {section}:\n"
        for detail in details:
            for key, value in detail.items():
                text_output += f"- {key}: {value}\n"

    return text_output


# Function to combine real facts and generated background
def addBackgroundToFacts():
    # Step 1: Get real facts
    essential_info = getRealFacts()

    # Step 2: Generate made-up background
    raw_background = generateMadeUpBackground(essential_info)

    # Step 3: Parse generated background into structured JSON
    parsed_background = parseGeneratedBackground(raw_background)

    # Step 4: Add the parsed background to the real facts
    essential_info["made_up_background"] = parsed_background

    # Step 5: Convert the result to a readable text format
    return convert_to_text(essential_info)


# Example usage
#final_data = addBackgroundToFacts()
#print(final_data)
