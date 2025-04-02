from collections import defaultdict


def parse_results(table: dict, names: dict, contest: dict) -> dict:
    final_table = defaultdict(list)

    score = contest['type']

    final_table['contestName'] = [ contest['name'] ]
    final_table['type'] = [ score ]

    for row in table:
        first_participant_name = row['party']['members'][0]['name'] \
            if 'name' in row['party']['members'][0] \
            else row['party']['members'][0]['handle']

        name = row['party']['teamName'] if 'teamName' in row['party'] else first_participant_name

        final_table['name'].append(name)
        final_table['score'].append(row['points'])

        for problem, name in zip(row['problemResults'], names):
            if score == 'ICPC':
                if problem['points'] == '1':
                    final_table[name['name']].append('+')
                else:
                    final_table[name['name']].append('-')
            else:
                final_table[name['name']].append(problem['points'])

    return final_table
