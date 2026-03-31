#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <chrono>
#include <string>
#include <vector>

bool WriteAll(int fd, const std::string& text);
bool ReadAll(int fd, std::string& text);

bool WriteFile(const std::string& path, const std::string& text);
bool ReadFile(const std::string& path, std::string& text);

std::string MakeFile(const std::string& prefix, const std::string& ext);
bool RunPreprocessor(const std::string& inputPath, const std::string& outputPath);

std::string PreprocessCode(const std::string& code);