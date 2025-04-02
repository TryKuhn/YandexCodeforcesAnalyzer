from collections import defaultdict


def parse_results(table: dict, names: list, contest: dict) -> tuple[str, dict]:
    final_table = defaultdict(list)

    score = 'IOI'
    for row in table['rows']:
        for problem in row['problemResults']:
            if problem['status'] == 'NOT_SUBMITTED':
                problem['score'] = '0'
            if problem['score'] == '':
                score = 'ICPC'

    final_table['contestName'] = [ contest['name'] ]
    final_table['type'] = [ score ]

    for row in table['rows']:
        final_table['name'].append(row['participantInfo']['name'])
        final_table['score'].append(int(row['score']) if score == 'IOI' else 0)

        for problem, name in zip(row['problemResults'], names):
            if score == 'ICPC':
                if problem['status'] == 'ACCEPTED':
                    final_table['score'][-1] += 1
                    final_table[name[0]].append('+')
                else:
                    final_table[name[0]].append('-')
            else:
                final_table[name[0]].append(problem['score'])

    return score, final_table
