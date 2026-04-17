#include "call_graph.h"

#include <algorithm>
#include <functional>

namespace {

void CollectDeclaredFunctions(const AstNode* node, std::unordered_set<std::string>& declared) {
    if (node == nullptr) {
        return;
    }

    if (node->type == AstNodeType::kFunctionDecl && !node->raw_name.empty()) {
        declared.insert(node->raw_name);
    }

    for (const auto& child : node->children) {
        CollectDeclaredFunctions(child.get(), declared);
    }
}

void CollectCallsInSubtree(const AstNode* node, std::vector<std::string>& calls) {
    if (node == nullptr) {
        return;
    }

    if (node->type == AstNodeType::kCallExpr && !node->raw_name.empty()) {
        calls.push_back(node->raw_name);
    }

    for (const auto& child : node->children) {
        CollectCallsInSubtree(child.get(), calls);
    }
}

void CollectEdges(
    const AstNode* node,
    const std::unordered_set<std::string>& declared,
    std::unordered_map<std::string, int>& in_degree,
    std::unordered_map<std::string, int>& out_degree,
    std::unordered_map<std::uint64_t, int>& edge_hash_freq,
    int& edges_cnt
) {
    if (node == nullptr) {
        return;
    }

    if (node->type == AstNodeType::kFunctionDecl && !node->raw_name.empty()) {
        const std::string& caller = node->raw_name;
        std::vector<std::string> calls;
        CollectCallsInSubtree(node, calls);

        for (const std::string& callee : calls) {
            if (declared.find(callee) == declared.end()) {
                continue;
            }

            ++edges_cnt;
            ++out_degree[caller];
            ++in_degree[callee];

            const std::uint64_t edge_hash = static_cast<std::uint64_t>(std::hash<std::string>{}(caller + "->" + callee));
            ++edge_hash_freq[edge_hash];
        }

        if (in_degree.find(caller) == in_degree.end()) {
            in_degree[caller] = 0;
        }
        if (out_degree.find(caller) == out_degree.end()) {
            out_degree[caller] = 0;
        }
    }

    for (const auto& child : node->children) {
        CollectEdges(child.get(), declared, in_degree, out_degree, edge_hash_freq, edges_cnt);
    }
}

std::unordered_map<int, int> BuildDegreeHistogram(const std::unordered_map<std::string, int>& degree_by_function) {
    std::unordered_map<int, int> hist;
    for (const auto& [name, degree] : degree_by_function) {
        (void)name;
        ++hist[degree];
    }
    return hist;
}

}  // namespace

CallGraphFeatures BuildCallGraphFeatures(const AstTree& tree) {
    CallGraphFeatures ret;
    if (!tree.parse_ok || tree.root == nullptr) {
        return ret;
    }

    std::unordered_set<std::string> declared;
    CollectDeclaredFunctions(tree.root.get(), declared);

    ret.parse_ok = true;
    ret.functions_cnt = static_cast<int>(declared.size());

    std::unordered_map<std::string, int> in_degree;
    std::unordered_map<std::string, int> out_degree;
    CollectEdges(tree.root.get(), declared, in_degree, out_degree, ret.edge_hash_freq, ret.edges_cnt);

    ret.in_degree_hist = BuildDegreeHistogram(in_degree);
    ret.out_degree_hist = BuildDegreeHistogram(out_degree);
    return ret;
}

