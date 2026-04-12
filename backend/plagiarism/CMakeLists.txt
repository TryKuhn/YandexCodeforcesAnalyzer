cmake_minimum_required(VERSION 3.20)

project(plagiarism LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Clang REQUIRED CONFIG)
find_package(Boost REQUIRED)

add_executable(plagiarism
        main.cpp

        outdated_metrics/levenshtein_similarity.cpp

        preprocessing/comments.cpp
        preprocessing/line_endings.cpp
        preprocessing/lines.cpp
        preprocessing/normalize.cpp
        preprocessing/string_normalizer.cpp
        preprocessing/cpp_preprocessor.cpp

        submission_builder/submission_builder.cpp
        submission_builder/submission_stages.cpp

        tokenizer/tokenizer.cpp
        tokenizer/normalize_tokens.cpp
        tokenizer/token_features_builder.cpp

        similarity/compare_submissions.cpp
        similarity/metrics.cpp
        ast/ast_analyzer.cpp

        preprocessing/cpp_preprocessor.h
        preprocessing/string_normalizer.h
        tokenizer/tokenizer.h
        tokenizer/normalize_tokens.h
        models/token.h
        models/submission_data.h
        models/submission_features.h
        models/similar_submission_pair.h
        models/similarity_result.h
        models/winnowing_features.h
        similarity/winnowing.h
        similarity/winnowing.cpp
        similarity/lsh.h
        similarity/lsh.cpp
)

target_include_directories(plagiarism PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/metrics
        ${CMAKE_CURRENT_SOURCE_DIR}/models
        ${CMAKE_CURRENT_SOURCE_DIR}/preprocessing
        ${CMAKE_CURRENT_SOURCE_DIR}/submission_builder
        ${CMAKE_CURRENT_SOURCE_DIR}/tokenizer
        ${Boost_INCLUDE_DIRS}
        ${CLANG_INCLUDE_DIRS}
)

target_link_libraries(plagiarism PRIVATE
        libclang
        Boost::headers
)