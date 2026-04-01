cmake_minimum_required(VERSION 3.20)

project(plagiarism LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Clang REQUIRED CONFIG)

add_executable(plagiarism
        main.cpp

        metrics/levenshtein_similarity.cpp

        preprocessing/comments.cpp
        preprocessing/line_endings.cpp
        preprocessing/lines.cpp
        preprocessing/normalize.cpp
        preprocessing/string_normalizer.cpp

        submission_builder/submission_builder.cpp

        tokenizer/tokenizer.cpp
        preprocessing/string_normalizer.h
        preprocessing/cpp_preprocessor.cpp
        preprocessing/cpp_preprocessor.h
        tokenizer/tokenizer.h
        models/token.h
        models/submission_data.h
        tokenizer/normalize_tokens.cpp
        tokenizer/normalize_tokens.h
        models/submission_features.h
)

target_include_directories(plagiarism PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/metrics
        ${CMAKE_CURRENT_SOURCE_DIR}/models
        ${CMAKE_CURRENT_SOURCE_DIR}/preprocessing
        ${CMAKE_CURRENT_SOURCE_DIR}/submission_builder
        ${CMAKE_CURRENT_SOURCE_DIR}/tokenizer
        ${CLANG_INCLUDE_DIRS}
)

target_link_libraries(plagiarism PRIVATE
        libclang
)