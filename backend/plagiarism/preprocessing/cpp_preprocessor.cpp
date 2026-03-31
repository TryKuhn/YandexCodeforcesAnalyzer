#include "cpp_preprocessor.h"

bool WriteAll(int fd, const std::string& text) {
    size_t pos = 0;

    while (pos < text.size()) {
        ssize_t written = write(fd, text.data() + pos, text.size() - pos);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            //TODO
            return false;
        }
        pos += static_cast<size_t>(written);
    }
    return true;
}


bool ReadAll(int fd, std::string& text) {
    text.clear();
    char buffer[4096];

    while (true) {
        ssize_t r = read(fd, buffer, sizeof(buffer));
        if (r == 0) {
            break;
        }
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            //TODO
            return false;
        }
        text.append(buffer, r);
    }

    return true;
}

bool WriteFile(const std::string& path, const std::string& text) {
    int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        return false;
    }

    bool ok = WriteAll(fd, text);
    close(fd);
    return ok;
}

bool ReadFile(const std::string& path, std::string& text) {
    int fd = open(path.c_str(), O_RDONLY);
    if (fd < 0) {
        return false;
    }

    bool ok = ReadAll(fd, text);
    close(fd);
    return ok;
}

std::string MakeFile(const std::string& prefix, const std::string& ext) {
    long long t = std::chrono::steady_clock::now().time_since_epoch().count();
    return "./" + prefix + "_" + std::to_string(getpid()) + "_" + std::to_string(t) + ext;
}

bool RunPreprocessor(const std::string& inputPath, const std::string& outputPath) {
    pid_t pid = fork();

    if (pid < 0) {
        return false;
    }

    if (pid == 0) {
        char* argv[] = {
            (char*)"g++",
            (char*)"-E",
            (char*)"-P",
            (char*)"-x",
            (char*)"c++",
            (char*)inputPath.c_str(),
            (char*)"-o",
            (char*)outputPath.c_str(),
            nullptr
        };

        execvp("g++", argv);

        _exit(127);
    }

    int status = 0;

    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR) {
            continue;
        }
        return false;
    }

    if (!WIFEXITED(status)) {
        return false;
    }

    return WEXITSTATUS(status) == 0;
}
std::string PreprocessCode(const std::string& code) {
    std::string inputPath = MakeFile("pp_input", ".cpp");
    std::string outputPath = MakeFile("pp_output", ".ii");

    if (!WriteFile(inputPath, code)) {
        return "";
    }

    if (!RunPreprocessor(inputPath, outputPath)) {
        unlink(inputPath.c_str());
        unlink(outputPath.c_str());
        return "";
    }

    std::string result;
    if (!ReadFile(outputPath, result)) {
        unlink(inputPath.c_str());
        unlink(outputPath.c_str());
        return "";
    }

    unlink(inputPath.c_str());
    unlink(outputPath.c_str());

    return result;
}