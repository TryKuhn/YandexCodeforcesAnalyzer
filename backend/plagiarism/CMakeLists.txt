cmake_minimum_required(VERSION 3.20)

project(plagiarism LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Clang REQUIRED CONFIG)
find_package(Boost REQUIRED)
find_package(pybind11 CONFIG QUIET)

set(PLAGIARISM_CORE_SOURCES
        outdated_metrics/levenshtein_similarity.cpp

        preprocessing/comments.cpp
        preprocessing/line_endings.cpp
        preprocessing/lines.cpp
        preprocessing/normalize.cpp
        preprocessing/string_normalizer.cpp
        preprocessing/cpp_preprocessor.cpp
        preprocessing/llvm_ir_pipeline.cpp

        submission_builder/submission_builder.cpp
        submission_builder/submission_stages.cpp

        tokenizer/tokenizer.cpp
        tokenizer/normalize_tokens.cpp
        tokenizer/token_features_builder.cpp

        similarity/compare_submissions.cpp
        similarity/metrics.cpp
        similarity/winnowing.cpp
        similarity/lsh.cpp

        ast/ast_analyzer.cpp
        ast/ast_hashing.cpp

        submission_loader/submission_loader.cpp
)

add_library(plagiarism_core STATIC
        ${PLAGIARISM_CORE_SOURCES}
)

target_include_directories(plagiarism_core PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/metrics
        ${CMAKE_CURRENT_SOURCE_DIR}/models
        ${CMAKE_CURRENT_SOURCE_DIR}/preprocessing
        ${CMAKE_CURRENT_SOURCE_DIR}/submission_builder
        ${CMAKE_CURRENT_SOURCE_DIR}/tokenizer
        ${Boost_INCLUDE_DIRS}
        ${CLANG_INCLUDE_DIRS}
)

target_link_libraries(plagiarism_core PUBLIC
        libclang
        Boost::headers
)

set_target_properties(plagiarism_core PROPERTIES
        POSITION_INDEPENDENT_CODE ON
)

add_executable(plagiarism
        main.cpp
)

target_link_libraries(plagiarism PRIVATE
        plagiarism_core
)

if(pybind11_FOUND)
    pybind11_add_module(plagiarism_cpp
            similarity/bindings.cpp
    )

    target_link_libraries(plagiarism_cpp PRIVATE
            plagiarism_core
    )
endif()

