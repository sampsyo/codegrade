#!/usr/bin/env python3

import click
import os
import tempfile
import shutil
import subprocess
import signal
import csv
from collections import namedtuple

DIRECTORY = click.Path(file_okay=False, exists=True)
TIMEOUT = b'<timeout>'

Result = namedtuple('Result', ['test_output', 'build_output', 'build_error'])


def copy_all(src_dir, dest_dir):
    """Copy everything from `src_dir` into `dest_dir`."""

    for name in os.listdir(src_dir):
        src_path = os.path.join(src_dir, name)
        if os.path.isdir(src_path):
            shutil.copytree(
                src_path, os.path.join(dest_dir, name),
                lambda s, d: shutil.copy(s, d, follow_symlinks=False)
            )
        else:
            shutil.copy(src_path, dest_dir, follow_symlinks=False)


def call(args, shell=False, cwd=None, timeout=None):
    """Run a command and return its output.

    Unlike `subprocess.call` and its variants, this runs the subprocess
    in a new process group. The entire subprocess group is killed when
    it times out.
    """

    with subprocess.Popen(args, shell=shell, cwd=cwd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          preexec_fn=os.setsid) as proc:
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            raise

        if proc.returncode:
            raise subprocess.CalledProcessError(
                returncode=proc.returncode,
                cmd=args,
                output=stdout,
            )

    return stdout


def run_tests(submission_path, submission_names, context_dir, build_cmd,
              test_cmd, test_paths, timeout):
    """Run all the grading tests for a specific submission. Return a
    Result object.

    If any test fails, it will be missing from the output mapping in the
    Result. If the build fails, then all tests will be missing.
    """

    # Copy files into a temporary directory.
    with tempfile.TemporaryDirectory() as work_dir:
        # Include the context.
        if context_dir:
            copy_all(context_dir, work_dir)

        # Include the student submission files.
        if submission_names:
            # Explicit list of files to include.
            for sub_name in submission_names:
                src_path = os.path.join(submission_path, sub_name)
                if not os.path.exists(src_path):
                    msg = 'missing: {}'.format(sub_name) \
                        .encode('utf8', 'ignore')
                    return Result({}, msg, 1)
                shutil.copy(src_path, work_dir)
        else:
            # Copy everything.
            copy_all(submission_path, work_dir)

        # Run the build command, if any.
        if build_cmd:
            try:
                build_output = call(build_cmd, shell=True, cwd=work_dir)
            except subprocess.CalledProcessError as exc:
                print('build failed')
                return Result({}, exc.output, exc.returncode)

        # Run the tests.
        test_output = {}
        if test_paths:
            # Run one test per file. The command gets the test filename
            # as an argument.
            for test_path in test_paths:
                name = os.path.basename(test_path)
                print(name)
                try:
                    test_output[test_path] = call(
                        ['sh', '-c', test_cmd, test_path],
                        timeout=timeout, cwd=work_dir,
                    )
                except subprocess.CalledProcessError:
                    print('test {} failed'.format(name))
                except subprocess.TimeoutExpired:
                    print('test {} timed out'.format(name))
                    test_output[test_path] = TIMEOUT

        else:
            # Run a single test command.
            try:
                test_output['-'] = call(
                    test_cmd, shell=True, timeout=timeout, cwd=work_dir
                )
            except subprocess.CalledProcessError:
                print('test failed')
            except subprocess.TimeoutExpired:
                print('test timed out')
                test_output['-'] = TIMEOUT

    return Result(test_output, build_output, 0)


def compare_output(sol_out, sub_res):
    """Compare the test results (a Result object) for a submission with
    the ground-truth results (a filename/output mapping).

    Return two things:
    - A mapping from test paths to single-letter strings indicating the
      status: Pass, Fail, Error, or Timeout.
    - A human-readable log describing the comparison results.
    """

    log = ['== build log ==',
           sub_res.build_output.decode('utf8', 'ignore').strip()]

    # Check for build failure.
    if sub_res.build_error:
        log += ['build failed']
        results = {k: 'E' for k in sol_out}
        return results, '\n'.join(log)

    results = {}
    correct = 0
    for test_path in sol_out:
        name = os.path.basename(test_path)

        if test_path in sub_res.test_output:
            sol = sol_out[test_path]
            sub = sub_res.test_output[test_path]
            if sub == TIMEOUT:
                results[test_path] = 'T'
                log.append('{}: timed out'.format(name))

            elif sol == sub:
                results[test_path] = 'P'
                correct += 1

            else:
                results[test_path] = 'F'

                sub_s = sub.decode('utf8', 'ignore').strip()
                sol_s = sol.decode('utf8', 'ignore').strip()
                log.append('')
                log.append('=== {} ==='.format(name))
                log.append(sub_s)
                log.append('-- expected --')
                log.append(sol_s)

        else:
            results[test_path] = 'E'
            log.append('{}: test execution failed'.format(name))

    log.append('')
    log.append('{}/{}'.format(correct, len(sol_out)))

    return results, '\n'.join(log)


@click.command()
@click.option('--file', type=str, metavar='<name>', multiple=True,
              help='student submission filename')
@click.option('--context', type=DIRECTORY, metavar='<dir>', required=True,
              help='directory with scaffolding files')
@click.option('--build', type=str, metavar='<cmd>', default='make',
              help='command to build submissions')
@click.option('--tests', type=DIRECTORY, metavar='<dir>', required=True,
              help='directory of tests to run')
@click.option('--test', type=str, metavar='<cmd>', required=True,
              help='command to run each test')
@click.option('--solution', type=DIRECTORY, metavar='<dir>',
              help='pseudo-submission with correct solution')
@click.option('--logs', type=click.Path(file_okay=False), metavar='<dir>',
              help='directory to write log files')
@click.option('--summary', type=click.Path(dir_okay=False, writable=True),
              help='CSV file to write summary data')
@click.option('--timeout', type=float, default=5.0,
              help='seconds to wait for each test')
@click.option('--single/--multiple', default=False,
              help='grade one submission, not a parent directory')
@click.argument('submissions', type=DIRECTORY, metavar='<dir>')
def codegrade(submissions, file, context, build, test, tests, solution,
              logs, summary, timeout, single):
    # Load test filenames.
    test_paths = [os.path.abspath(os.path.join(tests, name))
                  for name in sorted(os.listdir(tests))
                  if not name.startswith('.')]

    # Run the solution, if we have one.
    if solution:
        print('solution')
        sol_res = run_tests(solution, file, context, build, test, test_paths,
                            timeout)

    # Start the summary CSV.
    if summary:
        test_names = [os.path.basename(p) for p in test_paths]
        summary_file = open(summary, 'w')
        summary_writer = csv.DictWriter(
            summary_file,
            ['id', 'score'] + test_names,
        )
        summary_writer.writeheader()

    # Just grading one submission, or get the submissions by listing the
    # directory?
    if single:
        sub_dirs = [submissions]
    else:
        sub_dirs = [os.path.join(submissions, d)
                    for d in os.listdir(submissions)]
        sub_dirs = filter(os.path.isdir, sub_dirs)

    # Run submissions.
    for path in sub_dirs:
        name = os.path.basename(path)
        print(name)
        sub_res = run_tests(path, file, context, build, test, test_paths,
                            timeout)

        # Compare outputs to the solution.
        if solution:
            results, log = compare_output(sol_res.test_output, sub_res)

            # Write the summary row.
            if summary:
                summary_writer.writerow({
                    'id': name,
                    'score': sum(r == 'P' for r in results.values()),
                    **{os.path.basename(k): v for k, v in results.items()},
                })
                summary_file.flush()

            # Write log file.
            if logs:
                os.makedirs(logs, exist_ok=True)
                log_path = os.path.join(logs, '{}.txt'.format(name))
                with open(log_path, 'w') as f:
                    f.write(log)


if __name__ == '__main__':
    codegrade()
