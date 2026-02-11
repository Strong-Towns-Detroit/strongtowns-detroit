"""Parse BZA meeting minutes text into structured case data."""

import re


def parse_meeting_date(filename):
    """Extract meeting date from filename (assumes yyyy-mm-dd prefix).

    Returns the date string or "Unknown".
    """
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
    if date_match:
        return date_match.group(1)
    return "Unknown"


def parse_cases(text, meeting_date, source_file):
    """Parse individual cases from BZA meeting minutes text.

    Returns a list of dicts with keys: case_number, meeting_date,
    council_district, petitioner, location, legal_description,
    proposal, action, affirmative_votes, negative_votes, decision,
    source_file, raw_text.
    """
    cases = []

    # Split text by case numbers
    case_pattern = r'(CASE NO\.?:\s*[^\n]+)'
    case_splits = re.split(case_pattern, text)

    for i in range(1, len(case_splits), 2):
        if i + 1 >= len(case_splits):
            break

        case_header = case_splits[i]
        case_content = case_splits[i + 1]
        full_case = case_header + case_content

        # Extract case number
        case_num_match = re.search(r'CASE NO\.?:\s*([^\s-]+(?:-\d+)?)', case_header)
        case_number = case_num_match.group(1).strip() if case_num_match else "Unknown"

        # Extract council district
        district_match = re.search(r'Council District\s*#?(\d+|At Large)', full_case, re.IGNORECASE)
        district = district_match.group(1).strip() if district_match else "Unknown"

        # Extract petitioner
        petitioner = "Unknown"
        petitioner_match = re.search(
            r'(?:BZA\s+)?(?:PETITIONER|APPLICANT):\s*([^\n]+)', full_case, re.IGNORECASE
        )
        if petitioner_match:
            petitioner = petitioner_match.group(1).strip()
        else:
            petitioner_match = re.search(
                r'CASE NO\.?:\s*[^\n]+\n+(?:BZA\s+)?(?:PETITIONER|APPLICANT):\s*([^\n]+)',
                full_case, re.IGNORECASE,
            )
            if petitioner_match:
                petitioner = petitioner_match.group(1).strip()

        if petitioner != "Unknown":
            petitioner = re.sub(r'\s+', ' ', petitioner).strip()

        # Extract location
        location_match = re.search(r'LOCATION:\s*([^\n]+)', full_case)
        location = location_match.group(1).strip() if location_match else "Unknown"

        # Extract legal description
        legal_match = re.search(
            r'LEGAL DESCRIPTION OF PROPERTY:\s*([^P][^\n]+(?:\n(?!PROPOSAL:)[^\n]+)*)', full_case
        )
        legal_description = legal_match.group(1).strip() if legal_match else "Unknown"
        legal_description = re.sub(r'\s+', ' ', legal_description)

        # Extract proposal
        proposal_match = re.search(r'PROPOSAL:\s*(.*?)(?=ACTION OF THE BOARD:|$)', full_case, re.DOTALL)
        proposal = proposal_match.group(1).strip() if proposal_match else "Unknown"
        proposal = re.sub(r'\s+', ' ', proposal)

        # Extract action
        action_match = re.search(
            r'ACTION\s+OF\s+THE\s+BOARD:\s*(.*?)(?=\s*Affirmative:|$)',
            full_case, re.DOTALL | re.IGNORECASE,
        )
        action = action_match.group(1).strip() if action_match else "Unknown"
        action = re.sub(r'\s+', ' ', action)

        # Extract vote counts
        affirmative_match = re.search(r'Affirmative:\s*([^\n]+)', full_case)
        affirmative_votes = affirmative_match.group(1).strip() if affirmative_match else "Unknown"

        negative_match = re.search(r'Negative:\s*([^\n]*)', full_case)
        negative_votes = negative_match.group(1).strip() if negative_match else "None"
        if not negative_votes or negative_votes.lower() == 'none':
            negative_votes = "None"

        # Extract final decision
        decision_lines = full_case.split('\n')
        decision = "Unknown"
        for line in reversed(decision_lines):
            line = line.strip()
            if 'GRANTED' in line.upper() or 'DENIED' in line.upper() or 'APPROVED' in line.upper():
                decision = line.strip()
                break

        case_data = {
            'case_number': case_number,
            'meeting_date': meeting_date,
            'council_district': district,
            'petitioner': petitioner,
            'location': location,
            'legal_description': legal_description,
            'proposal': proposal,
            'action': action,
            'affirmative_votes': affirmative_votes,
            'negative_votes': negative_votes,
            'decision': decision,
            'source_file': source_file,
            'raw_text': full_case.strip(),
        }
        cases.append(case_data)

    return cases
