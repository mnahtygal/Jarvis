#define _GNU_SOURCE

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define REPOSITORY_ROOT "/home/mnahtygal/jarvis"
#define PYTHON_PATH REPOSITORY_ROOT "/.venv/bin/python"
#define API_PATH REPOSITORY_ROOT "/api.py"
#define ISOLATION_TEST_PATH REPOSITORY_ROOT "/tests/test_developer_agent_candidate_verification.py"
#define REPOSITORY_PYTHONPATH REPOSITORY_ROOT

static int set_fixed_environment(void) {
    if (clearenv() != 0) {
        return -1;
    }
    if (setenv("HOME", "/home/mnahtygal", 1) != 0 ||
        setenv("LANG", "C.UTF-8", 1) != 0 ||
        setenv("LC_ALL", "C.UTF-8", 1) != 0 ||
        setenv("PATH", "/usr/bin:/bin", 1) != 0 ||
        setenv("PYTHONPATH", REPOSITORY_PYTHONPATH, 1) != 0 ||
        setenv("PYTHONNOUSERSITE", "1", 1) != 0 ||
        setenv("PYTHONSAFEPATH", "1", 1) != 0) {
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    char *const api_argv[] = {PYTHON_PATH, API_PATH, NULL};
    char *const verify_argv[] = {
        PYTHON_PATH,
        "-m",
        "pytest",
        "-q",
        ISOLATION_TEST_PATH,
        NULL,
    };

    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--verify-candidate-isolation") != 0)) {
        fputs("jarvis-api-entry: unsupported argument\n", stderr);
        return 64;
    }
    if (chdir(REPOSITORY_ROOT) != 0 || set_fixed_environment() != 0) {
        fputs("jarvis-api-entry: fixed runtime unavailable\n", stderr);
        return 69;
    }
    if (argc == 1) {
        execv(PYTHON_PATH, api_argv);
    } else {
        if (setenv("JARVIS_SYSTEM_ISOLATION_VERIFY", "1", 1) != 0) {
            fputs("jarvis-api-entry: fixed verification environment unavailable\n", stderr);
            return 69;
        }
        execv(PYTHON_PATH, verify_argv);
    }
    fprintf(stderr, "jarvis-api-entry: exec failed: %s\n", strerror(errno));
    return 69;
}
