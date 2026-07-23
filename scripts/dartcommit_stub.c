/* dartcommit_stub.c — the compiled executable of DartAutoCommit.app.
 *
 * WHY COMPILED (not a shell script): macOS TCC attributes a process's disk-access
 * rights to the code identity of the *executable image*. A shell-script bundle
 * executable is run by /bin/bash, so TCC sees /bin/bash and the .app's Full Disk
 * Access grant never applies (git/python against ~/Documents fail "Operation not
 * permitted"). A real Mach-O executable inside the signed bundle IS attributed to
 * the bundle, so the FDA grant applies — and the bash/git/python it spawns inherit
 * it (this stub stays alive as their parent / responsible process).
 *
 * It just runs the versioned logic: /bin/bash <repo>/scripts/auto_commit.sh, and
 * returns that script's exit code. auto_commit.sh remains the single source of truth.
 *
 * Built + ad-hoc signed into the bundle by scripts/install_dartcommit_app.sh.
 */
#include <stdio.h>
#include <stdlib.h>
#include <spawn.h>
#include <sys/wait.h>

extern char **environ;

int main(void) {
    const char *home = getenv("HOME");
    if (!home) return 2;

    char script[2048];
    int n = snprintf(script, sizeof script,
                     "%s/Documents/voltstream-ai/scripts/auto_commit.sh", home);
    if (n < 0 || (size_t)n >= sizeof script) return 2;

    char *argv[] = {"/bin/bash", script, NULL};
    pid_t pid;
    /* spawn (don't exec) so THIS process stays the responsible process holding the
       .app's FDA grant; the bash child and its git/python descendants inherit it. */
    if (posix_spawn(&pid, "/bin/bash", NULL, NULL, argv, environ) != 0) return 127;

    int status;
    if (waitpid(pid, &status, 0) < 0) return 1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
