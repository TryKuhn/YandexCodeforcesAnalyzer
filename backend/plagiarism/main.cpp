#include <functional>
#include <iomanip>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

#include "models/programming_language.h"
#include "models/submission.h"
#include "similarity/compare_submissions.h"
#include "submission_builder/submission_stages.h"

int main() {
    auto make_submission = [](int id, const std::string& code) {
        Submission s;
        s.id = id;
        s.language = ProgrammingLanguage::Cpp;
        s.rawCode = code;
        return s;
    };

    const std::string sum_base = R"(#include <iostream>
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

    const std::string sum_exact_copy = sum_base;

    const std::string sum_renamed = R"(#include <iostream>
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

    const std::string sum_define = R"(#include <iostream>
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

    const std::string sum_noise = R"(#include <iostream>
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

    const std::string sum_while = R"(#include <iostream>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    long long s = 0;
    while (n--) {
        int x;
        cin >> x;
        s += x;
    }
    cout << s << '\n';
    return 0;
})";

    const std::string sum_accumulate = R"(#include <iostream>
#include <numeric>
#include <vector>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
    }
    cout << accumulate(a.begin(), a.end(), 0LL) << '\n';
    return 0;
})";

    const std::string dijkstra = R"(#include <iostream>
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
        auto top = pq.top();
        pq.pop();
        long long d = top.first;
        int v = top.second;
        if (d != dist[v]) continue;
        for (auto edge : g[v]) {
            int to = edge.first;
            int w = edge.second;
            if (dist[to] > d + w) {
                dist[to] = d + w;
                pq.push({dist[to], to});
            }
        }
    }

    cout << (dist[t] == INF ? -1 : dist[t]) << '\n';
    return 0;
})";

    const std::string palindrome = R"(#include <iostream>
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

    const std::string prefix_function = R"(#include <iostream>
#include <string>
#include <vector>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    cin >> s;
    vector<int> p(s.size(), 0);
    for (int i = 1; i < (int)s.size(); ++i) {
        int j = p[i - 1];
        while (j > 0 && s[i] != s[j]) {
            j = p[j - 1];
        }
        if (s[i] == s[j]) {
            ++j;
        }
        p[i] = j;
    }

    for (int x : p) {
        cout << x << ' ';
    }
    cout << '\n';
    return 0;
})";

    const std::string sum_do_while = R"(#include <iostream>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    long long sum = 0;
    if (n > 0) {
        int i = 0;
        do {
            int x;
            cin >> x;
            sum += x;
            ++i;
        } while (i < n);
    }
    cout << sum << '\n';
    return 0;
})";

    const std::string sum_macro_heavy = R"(#include <iostream>
#include <vector>
#define RD(v) cin >> (v)
#define ADD(a, b) ((a) += (b))
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    RD(n);
    vector<int> a(n);
    long long ans = 0;
    for (int i = 0; i < n; ++i) {
        RD(a[i]);
        ADD(ans, a[i]);
    }
    cout << ans << '\n';
    return 0;
})";

    const std::string sum_with_unused_function = R"(#include <iostream>
#include <vector>
using namespace std;

long long unused_calc(const vector<int>& a) {
    long long z = 0;
    for (int x : a) {
        z += 1LL * x * x;
    }
    return z;
}

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

    const std::string bfs_grid = R"(#include <iostream>
#include <queue>
#include <string>
#include <vector>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    cin >> n >> m;
    vector<string> g(n);
    for (int i = 0; i < n; ++i) cin >> g[i];

    vector<vector<int>> dist(n, vector<int>(m, -1));
    queue<pair<int, int>> q;
    if (g[0][0] == '.') {
        dist[0][0] = 0;
        q.push({0, 0});
    }

    int dx[4] = {1, -1, 0, 0};
    int dy[4] = {0, 0, 1, -1};
    while (!q.empty()) {
        auto [x, y] = q.front();
        q.pop();
        for (int k = 0; k < 4; ++k) {
            int nx = x + dx[k], ny = y + dy[k];
            if (nx < 0 || ny < 0 || nx >= n || ny >= m) continue;
            if (g[nx][ny] == '#') continue;
            if (dist[nx][ny] != -1) continue;
            dist[nx][ny] = dist[x][y] + 1;
            q.push({nx, ny});
        }
    }

    cout << dist[n - 1][m - 1] << '\n';
    return 0;
})";

    const std::string lis_nlogn = R"(#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) cin >> a[i];

    vector<int> d;
    for (int x : a) {
        auto it = lower_bound(d.begin(), d.end(), x);
        if (it == d.end()) d.push_back(x);
        else *it = x;
    }

    cout << d.size() << '\n';
    return 0;
})";

    const std::string segment_tree_sum = R"(#include <iostream>
#include <vector>
using namespace std;

struct SegTree {
    int n;
    vector<long long> t;

    explicit SegTree(int n_) : n(n_), t(4 * n_, 0) {}

    void build(int v, int l, int r, const vector<int>& a) {
        if (l == r) {
            t[v] = a[l];
            return;
        }
        int m = (l + r) / 2;
        build(v * 2, l, m, a);
        build(v * 2 + 1, m + 1, r, a);
        t[v] = t[v * 2] + t[v * 2 + 1];
    }

    long long get(int v, int l, int r, int ql, int qr) const {
        if (ql > r || qr < l) return 0;
        if (ql <= l && r <= qr) return t[v];
        int m = (l + r) / 2;
        return get(v * 2, l, m, ql, qr) + get(v * 2 + 1, m + 1, r, ql, qr);
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, q;
    cin >> n >> q;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) cin >> a[i];

    SegTree st(n);
    st.build(1, 0, n - 1, a);

    while (q--) {
        int l, r;
        cin >> l >> r;
        --l; --r;
        cout << st.get(1, 0, n - 1, l, r) << '\n';
    }
    return 0;
})";

    const std::string topo_sort = R"(#include <iostream>
#include <queue>
#include <vector>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    cin >> n >> m;
    vector<vector<int>> g(n);
    vector<int> indeg(n, 0);

    for (int i = 0; i < m; ++i) {
        int u, v;
        cin >> u >> v;
        --u;
        --v;
        g[u].push_back(v);
        indeg[v]++;
    }

    queue<int> q;
    for (int i = 0; i < n; ++i) {
        if (indeg[i] == 0) q.push(i);
    }

    vector<int> order;
    while (!q.empty()) {
        int v = q.front();
        q.pop();
        order.push_back(v);
        for (int to : g[v]) {
            indeg[to]--;
            if (indeg[to] == 0) q.push(to);
        }
    }

    if ((int)order.size() != n) {
        cout << -1 << '\n';
        return 0;
    }

    for (int v : order) {
        cout << (v + 1) << ' ';
    }
    cout << '\n';
    return 0;
})";

    const std::string binary_search_answer = R"(#include <iostream>
using namespace std;

bool good(long long x, long long n) {
    return x * x >= n;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long n;
    cin >> n;
    long long l = 0, r = 2000000000LL;
    while (l < r) {
        long long m = l + (r - l) / 2;
        if (good(m, n)) r = m;
        else l = m + 1;
    }
    cout << l << '\n';
    return 0;
})";

    std::vector<Submission> submissions = {
        make_submission(1, sum_base),
        make_submission(2, sum_exact_copy),
        make_submission(3, sum_renamed),
        make_submission(4, sum_define),
        make_submission(5, sum_noise),
        make_submission(6, sum_while),
        make_submission(7, sum_accumulate),
        make_submission(8, dijkstra),
        make_submission(9, palindrome),
        make_submission(10, prefix_function),
        make_submission(11, sum_do_while),
        make_submission(12, sum_macro_heavy),
        make_submission(13, sum_with_unused_function),
        make_submission(14, bfs_grid),
        make_submission(15, lis_nlogn),
        make_submission(16, segment_tree_sum),
        make_submission(17, topo_sort),
        make_submission(18, binary_search_answer)
    };

    std::unordered_map<int, std::string> labels = {
        {1, "sum_base"},
        {2, "sum_exact_copy"},
        {3, "sum_renamed"},
        {4, "sum_define"},
        {5, "sum_noise"},
        {6, "sum_while"},
        {7, "sum_accumulate"},
        {8, "dijkstra"},
        {9, "palindrome"},
        {10, "prefix_function"},
        {11, "sum_do_while"},
        {12, "sum_macro_heavy"},
        {13, "sum_with_unused_function"},
        {14, "bfs_grid"},
        {15, "lis_nlogn"},
        {16, "segment_tree_sum"},
        {17, "topo_sort"},
        {18, "binary_search_answer"}
    };

    std::vector<SimilarSubmissionPair> pairs = compute_similarity_pairs(submissions, 0.0);

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "Found pairs: " << pairs.size() << "\n";
    for (const auto& p : pairs) {
        std::cout << p.first_submission_id << " (" << labels[p.first_submission_id] << ")"
                  << " - "
                  << p.second_submission_id << " (" << labels[p.second_submission_id] << ")"
                  << " => " << p.plagiarism_percent << "%\n";
    }

    return 0;
}
