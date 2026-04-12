#include <iomanip>
#include <iostream>
#include <unordered_map>
#include <vector>

#include "models/programming_language.h"
#include "models/submission.h"
#include "similarity/compare_submissions.h"

int main() {
    auto make_submission = [](int id, const std::string& code) {
        Submission s;
        s.id = id;
        s.language = ProgrammingLanguage::Cpp;
        s.rawCode = code;
        return s;
    };

    const std::string sum_vector_a = R"(#include <iostream>
#include <vector>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> a(n);
    long long ans = 0;
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
        ans += a[i];
    }
    cout << ans << '\n';
    return 0;
})";

    const std::string sum_vector_b = R"(#include <iostream>
#include <vector>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int len;
    cin >> len;
    vector<int> nums(len);
    long long total = 0;
    for (int idx = 0; idx < len; ++idx) {
        cin >> nums[idx];
        total += nums[idx];
    }
    cout << total << '\n';
    return 0;
})";

    const std::string sum_vector_exact_copy = sum_vector_a;

    const std::string sum_with_define = R"(#include <iostream>
#include <vector>
#define FAST_IO ios::sync_with_stdio(false); cin.tie(nullptr)
#define FOR(i, n) for (int i = 0; i < (n); ++i)
using namespace std;
int main() {
    FAST_IO;
    int n;
    cin >> n;
    vector<int> arr(n);
    long long answer = 0;
    FOR(i, n) {
        cin >> arr[i];
        answer += arr[i];
    }
    cout << answer << '\n';
    return 0;
})";

    const std::string sum_with_noise = R"(#include <iostream>
#include <vector>
using namespace std;

static int debug_unused(int x) {
    if (x < 0) return -x;
    return x;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> v(n);
    long long sum = 0;

    for (int i = 0; i < n; ++i) {
        cin >> v[i];
        sum += v[i];
    }

    if (false) {
        cout << debug_unused((int)sum) << '\n';
    }

    cout << sum << '\n';
    return 0;
})";

    const std::string dijkstra_graph = R"(#include <iostream>
#include <queue>
#include <vector>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    cin >> n >> m;
    vector<vector<pair<int, int>>> g(n);
    for (int i = 0; i < m; ++i) {
        int u, v, w;
        cin >> u >> v >> w;
        --u; --v;
        g[u].push_back({v, w});
        g[v].push_back({u, w});
    }

    int s, t;
    cin >> s >> t;
    --s; --t;

    const long long INF = (long long)4e18;
    vector<long long> dist(n, INF);
    priority_queue<pair<long long, int>, vector<pair<long long, int>>, greater<pair<long long, int>>> pq;
    dist[s] = 0;
    pq.push({0, s});

    while (!pq.empty()) {
        auto [d, v] = pq.top();
        pq.pop();
        if (d != dist[v]) continue;
        for (auto [to, w] : g[v]) {
            if (dist[to] > d + w) {
                dist[to] = d + w;
                pq.push({dist[to], to});
            }
        }
    }

    cout << (dist[t] == INF ? -1 : dist[t]) << '\n';
    return 0;
})";

    const std::string palindrome_check = R"(#include <iostream>
#include <string>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    cin >> s;
    int l = 0;
    int r = (int)s.size() - 1;
    bool ok = true;
    while (l < r) {
        if (s[l] != s[r]) {
            ok = false;
            break;
        }
        ++l;
        --r;
    }
    cout << (ok ? "YES" : "NO") << '\n';
    return 0;
})";

    std::vector<Submission> submissions = {
        make_submission(1, sum_vector_a),
        make_submission(2, sum_vector_b),
        make_submission(3, sum_vector_exact_copy),
        make_submission(4, sum_with_define),
        make_submission(5, sum_with_noise),
        make_submission(6, dijkstra_graph),
        make_submission(7, palindrome_check)
    };

    std::unordered_map<int, std::string> labels = {
        {1, "sum_base"},
        {2, "sum_renamed"},
        {3, "sum_exact_copy"},
        {4, "sum_define"},
        {5, "sum_noise"},
        {6, "dijkstra"},
        {7, "palindrome"}
    };

    std::vector<SimilarSubmissionPair> pairs = compute_similarity_pairs(submissions, 0.0);

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "Found pairs: " << pairs.size() << "\n";
    for (const auto& p : pairs) {
        std::cout << p.first_submission_id << " (" << labels[(int)p.first_submission_id] << ")"
                  << " - "
                  << p.second_submission_id << " (" << labels[(int)p.second_submission_id] << ")"
                  << " => " << p.plagiarism_percent << "%\n";
    }

    return 0;
}
