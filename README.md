codegrade.py, a simple autograder
=================================

This is a simple, flexible way to run lots of student code submissions on lots of tests. It doesn't try to compute grades or anything else smart; it just checks whether a command's output equals the output from a reference implementation.

It's written for Python 3. To install, I recommend cloning this repository and running something like this:

    $ pip3 install --user -e .

which will also get the only dependency, [Click][].

    $ pip3 install --user click

[click]: http://click.pocoo.org/5/

Here's the general philosophy. `codegrade.py` works by making temporary directories, copying a bunch of files in there, building the code, running some tests, and emitting a log of successes and failures. You have *context* files, which are the scaffolding that every student's code gets graded in, and *submission* files, which students upload---both are combined together for building and execution. You also have a reference *solution*, which looks like a student submission but is guaranteed to be correct. Finally, you have a directory full of *test files*, which you run by executing some shell command for each file.


Using It
--------

Everything is controlled with command-line options. I usually make a little shell script that invokes `codegrade.py` with a litany of arguments---something like this:

    #!/bin/sh
    codegrade \
        --context code \
        --file submission.ml \
        --tests tests \
        --test './prog $0' \
        --solution solution \
        --logs logs \
        --summary summary.csv \
        $@

The rest of this section is about all those arguments. For a quick reference, you can type `python3 codegrade.py --help`.

## Setting Up

First things first. You will need:

* `--context DIR`: Your *context* directory contains the scaffolding code that all students (and your solution) have in common. This is probably the starter code you handed out to the students for the assignment.
* `--tests DIR`: A directory containing *test files*. Each one should somehow represent a different input.
* `--test CMD`: A shell command for running a single test. The command gets passed the filename for the test, so you can use `$0` to refer to it. You'll definitely want to shell-escape the command string to avoid interpolation. For example, `--test './prog $0'` just says "run the built executable `prog` on every given test file."
* `--solution DIR`: A directory containing submission files with known-good, correct code. The program will use the output from this implementation as the reference output, so anything that differs from it will be "wrong."

And optionally:

* `--file NAME`: The name of a *submission file* to collect from each student's submission directory. If you omit this, then the program will take *everything* from each submission directory. You can also use `--file` multiple times to collect multiple specific files.
* `--build CMD`: The command to run *before* running any tests, to build the code. This is `make` by default, so you can also configure the build process by putting a `Makefile` in your context directory.

## Running

After all the flags, provide the path to the directory that contains all the student submission directories. The archives that our infrastructure at Cornell gives us, for example, look like this:

    + Submissions
    |-+ student1
      |-- code.ml
    |-+ student2
      |-- code.ml

and so on. So I provide the name of the `Submissions` directory here.

Alternatively, you might want to run just *one* submission at a time (when debugging, for example). Use the `--single` flag. For example, you might type `--single Submissions/student2/` instead of just `Submissions/`.

## Saving Output

This tool can produce *logs* for manual inspection and a *summary* for a high-level overview of test outcomes.

* `--logs DIR`: Produce a log file for each submission in this directory. The log includes the output from building the submission and the reference & actual output for every test where the output differs (i.e., for every *wrong* test).
* `--summary FILE`: Write a CSV file that summarizes the test outcome for every test, for every submission. Rows are students; columns are tests. Each cell contains one of P (pass; output matched), F (fail; output differed), E (error; test command exit status was nonzero), or T (timeout).

I usually find it helpful to load up the summary CSV into Numbers and colorize the cells by their contents. This visualization helps me quickly identify students who failed lots of tests or tests that lots of students failed.

## Configuring

Here's one other option you might not need to use.

* `--timeout SECONDS`: How long the tool should wait for test executions to complete before considering them a timeout. The default is 5.0 seconds.


Credits
-------

This is by [Adrian Sampson][adrian]. The license is [MIT][].

[adrian]: https://www.cs.cornell.edu/~asampson/
[mit]: https://opensource.org/licenses/MIT
