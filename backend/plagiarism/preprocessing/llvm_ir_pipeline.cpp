#include "llvm_ir_pipeline.h"

#include "cpp_preprocessor.h"

#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <string>

static bool RunCommand(char* const argv[]) {
    const pid_t pid = fork();
    if (pid < 0) {
        return false;
    }

    if (pid == 0) {
        execvp(argv[0], argv);
        _exit(127);
    }

    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR) {
            continue;
        }
        return false;
    }

    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

static bool EmitLlvmIr(const std::string& input_cpp, const std::string& output_ll) {
    char* argv[] = {
        (char*)"clang++",
        (char*)"-std=c++17",
        (char*)"-O0",
        (char*)"-Xclang",
        (char*)"-disable-O0-optnone",
        (char*)"-S",
        (char*)"-emit-llvm",
        (char*)input_cpp.c_str(),
        (char*)"-o",
        (char*)output_ll.c_str(),
        nullptr
    };
    return RunCommand(argv);
}

static bool OptimizeLlvmIr(const std::string& input_ll, const std::string& output_ll) {
    char* argv[] = {
        (char*)"opt",
        (char*)"-S",
        (char*)"-passes=mem2reg,instcombine,simplifycfg,adce",
        (char*)input_ll.c_str(),
        (char*)"-o",
        (char*)output_ll.c_str(),
        nullptr
    };
    return RunCommand(argv);
}

std::string BuildLlvmIrFromCode(const std::string& code) {
    const std::string cpp_path = MakeFile("ir_input", ".cpp");
    const std::string raw_ll_path = MakeFile("ir_raw", ".ll");
    const std::string opt_ll_path = MakeFile("ir_opt", ".ll");

    std::string result;
    if (!WriteFile(cpp_path, code)) {
        return "";
    }

    if (!EmitLlvmIr(cpp_path, raw_ll_path) || !OptimizeLlvmIr(raw_ll_path, opt_ll_path)) {
        unlink(cpp_path.c_str());
        unlink(raw_ll_path.c_str());
        unlink(opt_ll_path.c_str());
        return "";
    }

    if (!ReadFile(opt_ll_path, result)) {
        unlink(cpp_path.c_str());
        unlink(raw_ll_path.c_str());
        unlink(opt_ll_path.c_str());
        return "";
    }

    unlink(cpp_path.c_str());
    unlink(raw_ll_path.c_str());
    unlink(opt_ll_path.c_str());
    return result;
}
