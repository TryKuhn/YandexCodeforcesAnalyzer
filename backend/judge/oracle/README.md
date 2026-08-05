# Oracle suites

Solutions with known verdicts. The judge must give each one exactly the verdict
its filename claims, otherwise the regression gate fails (YCA-407).

## Layout

```
<problem>/
    problem.json          limits and tests
    checker.cpp           testlib checker
    solutions/
        <tag>_<name>.<ext>
```

## Tags

The prefix before the first underscore is the expected outcome:

| tag  | verdict | meaning                                  |
|------|---------|------------------------------------------|
| `ma` | OK      | main (jury) solution                     |
| `ok` | OK      | another accepted solution                |
| `wa` | WA      | wrong answer                             |
| `tl` | TLE     | too slow                                 |
| `ml` | MLE     | uses too much memory                     |
| `re` | RE      | crashes                                  |
| `pe` | PE      | right idea, output the checker cannot parse |

The extension picks the language: `.cpp` or `.py`.

## Rules for new solutions

A wrong solution must earn its verdict **honestly** — by really being slow, really
allocating memory, really crashing. No `assert(false)`, no `while(true){}` without
work, no artificial sleeps. If a verdict cannot be guaranteed, the solution does not
belong here.

## Running

```bash
./scripts/judge/run-oracle.py          # needs the judge service on :8001
```
