#define _GNU_SOURCE

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define UNSHARE_PATH "/usr/bin/unshare"
#define BWRAP_PATH "/usr/bin/bwrap"
#define WORKSPACE_PATH "/workspace"
#define MAX_PYTEST_ARGUMENTS 128U
#define MAX_ARGUMENT_BYTES 4096U
#define MAX_TOTAL_ARGUMENT_BYTES (32U * 1024U)
#define MAX_EXEC_ARGUMENTS 1024U

struct runtime_bind {
    const char *source;
    const char *destination;
};

#include "../runtime-manifest.h"

static void refuse(const char *reason) {
    fprintf(stderr, "jarvis-candidate-sandbox: %s\n", reason);
}

static bool trusted_root_file(const char *path) {
    struct stat details;
    return stat(path, &details) == 0 && S_ISREG(details.st_mode) &&
           details.st_uid == 0 && (details.st_mode & (S_IWGRP | S_IWOTH)) == 0 &&
           access(path, X_OK) == 0;
}

static bool parse_fd(const char *text, int *result) {
    char *end = NULL;
    long value;
    if (text == NULL || *text == '\0') {
        return false;
    }
    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value < 3 || value > 1024) {
        return false;
    }
    *result = (int)value;
    return true;
}

static bool validate_candidate_fd(int descriptor, char *fd_path, size_t fd_path_size) {
    struct stat descriptor_stat;
    struct stat resolved_stat;
    char target[PATH_MAX + 1];
    char resolved[PATH_MAX + 1];
    ssize_t length;
    int written;

    if (fstat(descriptor, &descriptor_stat) != 0 || !S_ISDIR(descriptor_stat.st_mode) ||
        descriptor_stat.st_uid != getuid() ||
        (descriptor_stat.st_mode & (S_IRWXG | S_IRWXO)) != 0 ||
        (descriptor_stat.st_mode & S_IRWXU) != S_IRWXU) {
        return false;
    }
    written = snprintf(fd_path, fd_path_size, "/proc/self/fd/%d", descriptor);
    if (written < 0 || (size_t)written >= fd_path_size) {
        return false;
    }
    length = readlink(fd_path, target, sizeof(target) - 1U);
    if (length <= 0 || (size_t)length >= sizeof(target) - 1U) {
        return false;
    }
    target[length] = '\0';
    if (strstr(target, " (deleted)") != NULL || realpath(target, resolved) == NULL ||
        strncmp(resolved, "/tmp/jarvis-candidate-", 22U) != 0 ||
        strchr(resolved + 22, '/') != NULL || stat(resolved, &resolved_stat) != 0 ||
        descriptor_stat.st_dev != resolved_stat.st_dev ||
        descriptor_stat.st_ino != resolved_stat.st_ino) {
        return false;
    }
    return true;
}

static bool safe_text(const char *value, size_t *total) {
    size_t index;
    size_t length;
    if (value == NULL || *value == '\0') {
        return false;
    }
    length = strlen(value);
    if (length > MAX_ARGUMENT_BYTES || *total > MAX_TOTAL_ARGUMENT_BYTES - length) {
        return false;
    }
    for (index = 0; index < length; ++index) {
        unsigned char character = (unsigned char)value[index];
        if (iscntrl(character) != 0 || strchr(";&|><`$", (int)character) != NULL) {
            return false;
        }
    }
    *total += length;
    return true;
}

static bool safe_relative_path(const char *value) {
    const char *cursor = value;
    const char *component = value;
    if (*value == '/' || *value == '@') {
        return false;
    }
    while (true) {
        if (*cursor == '/' || *cursor == '\0') {
            size_t length = (size_t)(cursor - component);
            if (length == 0U || (length == 1U && component[0] == '.') ||
                (length == 2U && component[0] == '.' && component[1] == '.')) {
                return false;
            }
            if (*cursor == '\0') {
                return true;
            }
            component = cursor + 1;
        }
        ++cursor;
    }
}

static bool validate_beneath_fd(int directory_fd, const char *value) {
    char copy[PATH_MAX + 1];
    char *selector;
    char *save = NULL;
    char *part;
    int current_fd;
    int next_fd;
    struct stat details;

    if (strlen(value) > PATH_MAX) {
        return false;
    }
    memcpy(copy, value, strlen(value) + 1U);
    selector = strstr(copy, "::");
    if (selector != NULL) {
        if (selector[2] == '\0') {
            return false;
        }
        *selector = '\0';
    }
    if (!safe_relative_path(copy)) {
        return false;
    }
    current_fd = dup(directory_fd);
    if (current_fd < 0) {
        return false;
    }
    part = strtok_r(copy, "/", &save);
    while (part != NULL) {
        char *next_part;
        if (fstatat(current_fd, part, &details, AT_SYMLINK_NOFOLLOW) != 0 ||
            S_ISLNK(details.st_mode)) {
            close(current_fd);
            return false;
        }
        next_part = strtok_r(NULL, "/", &save);
        if (next_part != NULL) {
            if (!S_ISDIR(details.st_mode)) {
                close(current_fd);
                return false;
            }
            next_fd = openat(current_fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
            if (next_fd < 0) {
                close(current_fd);
                return false;
            }
            close(current_fd);
            current_fd = next_fd;
        }
        part = next_part;
    }
    close(current_fd);
    return true;
}

static bool positive_integer(const char *value, unsigned maximum) {
    char *end = NULL;
    unsigned long number;
    errno = 0;
    number = strtoul(value, &end, 10);
    return errno == 0 && end != value && *end == '\0' && number >= 1U && number <= maximum;
}

static bool validate_pytest_arguments(int candidate_fd, int argc, char **argv) {
    int index;
    size_t total = 0U;
    if (argc < 0 || (unsigned)argc > MAX_PYTEST_ARGUMENTS) {
        return false;
    }
    for (index = 0; index < argc; ++index) {
        const char *argument = argv[index];
        if (!safe_text(argument, &total)) {
            return false;
        }
        if (strcmp(argument, "-q") == 0 || strcmp(argument, "-s") == 0 ||
            strcmp(argument, "-x") == 0 || strcmp(argument, "--collect-only") == 0 ||
            strcmp(argument, "--disable-warnings") == 0 ||
            strcmp(argument, "--strict-config") == 0 ||
            strcmp(argument, "--strict-markers") == 0) {
            continue;
        }
        if (strcmp(argument, "-k") == 0 || strcmp(argument, "-m") == 0) {
            ++index;
            if (index >= argc || !safe_text(argv[index], &total)) {
                return false;
            }
            continue;
        }
        if (strcmp(argument, "--ignore") == 0) {
            ++index;
            if (index >= argc || !safe_text(argv[index], &total) ||
                !validate_beneath_fd(candidate_fd, argv[index])) {
                return false;
            }
            continue;
        }
        if (strncmp(argument, "--ignore=", 9U) == 0) {
            if (!validate_beneath_fd(candidate_fd, argument + 9)) {
                return false;
            }
            continue;
        }
        if (strncmp(argument, "--maxfail=", 10U) == 0) {
            if (!positive_integer(argument + 10, 100U)) {
                return false;
            }
            continue;
        }
        if (strncmp(argument, "--tb=", 5U) == 0) {
            const char *value = argument + 5;
            if (strcmp(value, "auto") != 0 && strcmp(value, "long") != 0 &&
                strcmp(value, "short") != 0 && strcmp(value, "line") != 0 &&
                strcmp(value, "native") != 0 && strcmp(value, "no") != 0) {
                return false;
            }
            continue;
        }
        if (argument[0] == '-' || !validate_beneath_fd(candidate_fd, argument)) {
            return false;
        }
    }
    return true;
}

static bool append(char **execution, size_t *count, char *value) {
    if (*count + 1U >= MAX_EXEC_ARGUMENTS) {
        return false;
    }
    execution[*count] = value;
    *count += 1U;
    return true;
}

#define APPEND(value) do { if (!append(execution, &count, (char *)(value))) goto too_many; } while (0)

int main(int argc, char **argv) {
    int candidate_fd;
    int null_fd;
    int pytest_argc;
    int index;
    char fd_path[64];
    char loader_target[PATH_MAX + 1];
    char loader_link[PATH_MAX + 1];
    char **execution;
    size_t count = 0U;
    size_t bind_index;

    if (argc < 3 || strcmp(argv[1], "--candidate-fd") != 0 ||
        !parse_fd(argv[2], &candidate_fd)) {
        refuse("expected only --candidate-fd <open-directory-fd> and approved pytest arguments");
        return 64;
    }
    pytest_argc = argc - 3;
    if (!validate_candidate_fd(candidate_fd, fd_path, sizeof(fd_path))) {
        refuse("unsafe candidate directory identity");
        return 65;
    }
    if (!validate_pytest_arguments(candidate_fd, pytest_argc, argv + 3)) {
        refuse("unsupported pytest argument");
        return 64;
    }
    if (!trusted_root_file(UNSHARE_PATH) || !trusted_root_file(BWRAP_PATH) ||
        !trusted_root_file(JARVIS_BASE_PYTHON)) {
        refuse("fixed runtime identity is unsafe");
        return 69;
    }
    if (snprintf(loader_target, sizeof(loader_target), "%s/%s", JARVIS_SHARED_LIBRARIES,
                 JARVIS_LOADER_NAME) < 0 ||
        snprintf(loader_link, sizeof(loader_link), "/usr/lib/%s", JARVIS_LOADER_NAME) < 0) {
        refuse("fixed runtime path is unavailable");
        return 69;
    }
    null_fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
    if (null_fd < 0 || dup2(null_fd, STDIN_FILENO) < 0) {
        refuse("could not disable stdin");
        return 69;
    }
    if (null_fd != STDIN_FILENO) {
        close(null_fd);
    }
    if (clearenv() != 0 || setenv("PATH", "/usr/bin:/bin", 1) != 0 ||
        setenv("LANG", "C.UTF-8", 1) != 0 || setenv("LC_ALL", "C.UTF-8", 1) != 0) {
        refuse("could not create fixed environment");
        return 69;
    }
    execution = calloc(MAX_EXEC_ARGUMENTS, sizeof(*execution));
    if (execution == NULL) {
        refuse("out of memory");
        return 70;
    }

    APPEND(UNSHARE_PATH); APPEND("--user"); APPEND("--map-root-user"); APPEND("--net"); APPEND("--");
    APPEND(BWRAP_PATH); APPEND("--unshare-ipc"); APPEND("--unshare-pid"); APPEND("--unshare-uts");
    APPEND("--unshare-cgroup-try"); APPEND("--die-with-parent"); APPEND("--new-session");
    APPEND("--cap-drop"); APPEND("ALL"); APPEND("--clearenv");
    APPEND("--dir"); APPEND("/usr"); APPEND("--dir"); APPEND("/usr/lib");
    APPEND("--dir"); APPEND(JARVIS_SHARED_LIBRARIES); APPEND("--dir"); APPEND(JARVIS_STDLIB);
    APPEND("--symlink"); APPEND(loader_target); APPEND(loader_link);
    for (bind_index = 0U; bind_index < JARVIS_RUNTIME_BIND_COUNT; ++bind_index) {
        APPEND("--ro-bind"); APPEND(JARVIS_RUNTIME_BINDS[bind_index].source);
        APPEND(JARVIS_RUNTIME_BINDS[bind_index].destination);
    }
    APPEND("--ro-bind"); APPEND(JARVIS_STDLIB); APPEND(JARVIS_STDLIB);
    APPEND("--dir"); APPEND("/usr/bin"); APPEND("--ro-bind"); APPEND(JARVIS_BASE_PYTHON); APPEND(JARVIS_BASE_PYTHON);
    APPEND("--symlink"); APPEND("python3.12"); APPEND("/usr/bin/python3");
    APPEND("--symlink"); APPEND("usr/bin"); APPEND("/bin"); APPEND("--symlink"); APPEND("usr/lib"); APPEND("/lib");
    APPEND("--proc"); APPEND("/proc"); APPEND("--dev"); APPEND("/dev"); APPEND("--tmpfs"); APPEND("/tmp");
    APPEND("--dir"); APPEND("/tmp/home"); APPEND("--dir"); APPEND("/tmp/pycache"); APPEND("--dir"); APPEND("/opt");
    APPEND("--ro-bind"); APPEND(JARVIS_SITE_PACKAGES); APPEND("/opt/jarvis-site-packages");
    APPEND("--dir"); APPEND(WORKSPACE_PATH); APPEND("--ro-bind"); APPEND(fd_path); APPEND(WORKSPACE_PATH);
    APPEND("--chdir"); APPEND(WORKSPACE_PATH);
    APPEND("--setenv"); APPEND("HOME"); APPEND("/tmp/home");
    APPEND("--setenv"); APPEND("LANG"); APPEND("C.UTF-8"); APPEND("--setenv"); APPEND("LC_ALL"); APPEND("C.UTF-8");
    APPEND("--setenv"); APPEND("PATH"); APPEND("/usr/bin:/bin");
    APPEND("--setenv"); APPEND("PYTEST_DISABLE_PLUGIN_AUTOLOAD"); APPEND("1");
    APPEND("--setenv"); APPEND("PYTHONDONTWRITEBYTECODE"); APPEND("1");
    APPEND("--setenv"); APPEND("PYTHONNOUSERSITE"); APPEND("1");
    APPEND("--setenv"); APPEND("PYTHONPATH"); APPEND("/opt/jarvis-site-packages");
    APPEND("--setenv"); APPEND("PYTHONSAFEPATH"); APPEND("1");
    APPEND("--setenv"); APPEND("PYTHONPYCACHEPREFIX"); APPEND("/tmp/pycache");
    APPEND("--"); APPEND(JARVIS_BASE_PYTHON); APPEND("-m"); APPEND("pytest"); APPEND("-c"); APPEND("/dev/null");
    APPEND("--rootdir=/workspace"); APPEND("--confcutdir=/workspace"); APPEND("-p"); APPEND("no:cacheprovider");
    for (index = 0; index < pytest_argc; ++index) {
        APPEND(argv[index + 3]);
    }
    execution[count] = NULL;
    execv(UNSHARE_PATH, execution);
    refuse("fixed namespace launcher could not start");
    free(execution);
    return 69;

too_many:
    refuse("fixed execution vector exceeds limit");
    free(execution);
    return 70;
}
