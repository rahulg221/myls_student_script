import subprocess
import os
import sys
import tarfile
import re
from datetime import datetime
import pytz
import pandas as pd
import shutil

score = 0
execution_score_updated = False

def grade_repo(nid, clone_directory, testcase_names):
    global score
    grep_syscalls('myls.c', clone_directory)

    # Check if the repo exists
    repo_path = "myls_new"
    
    if os.path.isdir(repo_path):
      print("Repo exists: +1pts")
      score += 1
    else:
      print("Repo does not exist. No credit, see Dr. Gazzillo for questions and concerns.")
      return score
      
    # Check commit times to see if submitted past deadline
    if not check_commit_times(clone_directory):
      return score

    # Define the path to the Makefile
    makefile_path = os.path.join(clone_directory, "Makefile")

    if os.path.exists(makefile_path):
      print("Makefile found: +0.33pts")
      score += (1/3)
    elif not os.path.exists(makefile_path):
      makefile_path = os.path.join(clone_directory, "makefile")
      if os.path.exists(makefile_path):
        print("Makefile found: +0.33pts")
        score += (1/3)
    
    if not os.path.exists(makefile_path):
      print("Error: Makefile not found: +0pts")
      
    run_testcases(clone_directory, *testcase_names)
    
    total_possible_score = len(testcase_names) * 2 + 2
        
    #score += (1/3)
    #  print("Program runs successfully: +0.33pts")
    
    final_score = round(score, 2)
    
    print(f"TOTAL SCORE for {nid}: {final_score}/{total_possible_score}")
    return final_score

def run_testcases(clone_directory, *testcase_names):
    for testcase_name in testcase_names:
        # Check if the folder exists
        if not os.path.isdir(testcase_name):
            print(f"Warning: Testcase folder '{testcase_name}' does not exist.")
            continue

        # Locate 'expected_outputs.md' inside the test case folder
        expected_output_file = os.path.join(testcase_name, 'expected_outputs.md')
        
        if os.path.exists(expected_output_file):
            print(f"Found 'expected_outputs.md' in '{testcase_name}'.")

            # Read the content of 'expected_outputs.md'
            with open(expected_output_file, 'r') as f:
                file_content = f.read()

            # Extract each example from the file using regex
            total_outputs = re.findall(r'# Example (\d+)\n(.*?)(?=# Example |\Z)', file_content, re.DOTALL)

            # Store the first four examples in local variables
            relevant_outputs = {}
            for i in range(1, 5):
                relevant_outputs[i] = next((content for num, content in total_outputs if int(num) == i), None)
                #if relevant_outputs[i]:
                    #print(f"Stored content in relevant_outputs{i}: {relevant_outputs[i]}...")  # Print a snippet of the content
                    
            # Run 'run_myls_on_testcase' for each example if it exists
            for i in range(1, 5):
                testcase_output = relevant_outputs.get(i)
                if testcase_output:
                    run_myls_on_testcase(clone_directory, testcase_output, testcase_name, f'testcase{i}')
                    #print(f"Ran 'run_myls_on_testcase' for {testcase_name} with testcase{i}.")
        else:
            print(f"'expected_outputs.md' does not exist in the '{testcase_name}' folder.")

        print(f"Finished processing folder: {testcase_name}")
        
def run_myls_on_testcase(clone_directory, example, testcase_folder, testcase):
    global score, execution_score_updated
    
    # Construct the path to the 'contents' folder inside the 'private_testcases' directory
    contents_path = os.path.join(testcase_folder, testcase, 'contents')
    
    # Ensure that the contents folder exists
    if not os.path.isdir(contents_path):
        print(f"'contents' directory in {contents_path} does not exist.")
        return

    try:
        # Compile the myls program using the Makefile
        compile_command = f"make -C {clone_directory} myls"
        run_command(compile_command)
        
        # Define the path to the compiled myls executable
        myls_executable = os.path.join(clone_directory, "myls")

        # Ensure that the myls executable exists after compilation
        if not os.path.exists(myls_executable):
          print(f"Error: myls executable was not found at {myls_executable}.")
          return 0

        # Construct the command to run './myls' on the 'contents' folder
        command = f"{myls_executable} {contents_path}"

        # Run the compiled myls program
        success, output = run_command(command)
        
        if success:
          compare_output_with_example(output, example)
          
          if not execution_score_updated:
            score += 1/3  
            execution_score_updated = True  # Set the flag to only add points once on proof of execution
            print("Program ran successfully: +0.33pt")
        else: 
          print("Error: couldn't run command ./myls")
          return 0

    except Exception as e:
        print(f"An error occurred: {e}")
        
def compare_output_with_example(output, example):
    global score

    try:
        # Function to normalize text by removing extra spaces and special characters like '$'
        def normalize_and_sort(text):
            # Normalize each line: strip spaces, remove trailing '$'
            lines = [re.sub(r'\s+', '', line.strip().replace('$', '')) for line in text.splitlines() if line.strip()]
            # Sort the lines to ensure order doesn't matter
            return sorted(lines)

        # Normalize and sort both the output and the example
        output_normalized = normalize_and_sort(output)
        example_normalized = normalize_and_sort(example)

        # Use the number of lines in the example to calculate total lines
        total_lines = len(example_normalized)
        matching_lines = len(set(output_normalized) & set(example_normalized))

        # Calculate percentage of matching lines based on the number of lines in the example
        match_percentage = matching_lines / total_lines if total_lines > 0 else 0
        
        prorated_score = round((1/2) * match_percentage, 2)
        score += prorated_score
        print(f"Matched {matching_lines} out of {total_lines} lines: +{prorated_score}pts")
                
        # Output the differences between the student's output and the expected output for debugging
        print("Student output (stripped and sorted for comparison):")
        for line in output_normalized:
            print(f"'{line}'")
        print("Correct output (stripped and sorted for comparison):")
        for line in example_normalized:
            print(f"'{line}'")
    except Exception as e:
        # Catch any exception that occurs during execution
        print(f"Error comparing output: {e}")
        print("Skipping this comparison due to error.")
        
def grep_syscalls(source_file, clone_directory):
    global score
    score = 0  # Initialize score if it's not set elsewhere

    # Define syscall categories
    dir_syscalls = ['opendir', 'readdir']
    stat_syscalls = ['stat']
    file_syscalls = ['open', 'read', 'perror']

    # Combine all syscalls into a single list for the grep search
    all_syscalls = dir_syscalls + stat_syscalls + file_syscalls

    # Build the grep command
    syscall_pattern = '|'.join(all_syscalls)
    grep_command = f"grep -E '\\b({syscall_pattern})\\b' {source_file}"

    try:
        # Run the grep command in the clone_directory using cwd parameter
        result = subprocess.run(grep_command, shell=True, cwd=clone_directory, capture_output=True, text=True)

        # Check if the grep command succeeded
        if result.returncode == 0:
            # Extract all found syscalls from the output
            found_syscalls = re.findall(f'\\b({"|".join(all_syscalls)})\\b', result.stdout)
            unique_syscalls = list(set(found_syscalls))  # Remove duplicates

            print(f"Unique syscalls found: {unique_syscalls}")

            # Define the points for each syscall found
            points_per_syscall = (1 / 6) * (1 / 3)  # (1/6 * 1/3) points per syscall
            syscalls_found_count = len(unique_syscalls)

            # Award points for each unique syscall found
            total_pts = round(points_per_syscall * syscalls_found_count, 2)  # Rounded to 2 decimal places
            score += total_pts

            print(f"Found {syscalls_found_count} out of 6 total syscalls: +{total_pts}pts")

            return unique_syscalls
        elif result.returncode == 1:
            print(f"No syscalls found in {source_file}.")
            return []
        else:
            print(f"An error occurred while running grep: {result.stderr}")
            return []
    except Exception as e:
        print(f"An error occurred while grepping for syscalls: {e}")
        return []
        
def check_commit_times(cloned_directory):
    global score
    
    # Define the deadline as Oct 3, 2024, 11:59 PM EST
    deadline_str = "2024-10-03 23:59:59"
    est = pytz.timezone('US/Eastern')
    deadline = est.localize(datetime.strptime(deadline_str, '%Y-%m-%d %H:%M:%S'))

    # Run git log command to get the commit dates in the local timezone
    git_log_command = 'git log --pretty=format:"%ad" --date=local'
    
    print("Git commit history:")
    # Use the run_command function to execute the git log command
    success, git_log_output = run_command(git_log_command, cwd=cloned_directory)
    
    if not success:
        print(f"Failed to get git log from {cloned_directory}")
        score = 0
        return
    
    commit_dates = git_log_output.splitlines()
    
    if not commit_dates:
        print("No commits found in the repository.")
        score = 0
        return
    
    commits_before_deadline = 0
    commits_after_deadline = 0

    # Check all commits
    for commit_date_str in commit_dates:
        # Convert the commit date string from local time to EST for comparison
        commit_date = datetime.strptime(commit_date_str, '%a %b %d %H:%M:%S %Y')
        local_tz = pytz.timezone('US/Eastern') 
        
        # Compare commit time to the deadline in EST
        commit_date_est = local_tz.localize(commit_date)

        if commit_date_est <= deadline:
            commits_before_deadline += 1
        else:
            commits_after_deadline += 1

    # Logic to check commit times and print the corresponding message
    if commits_before_deadline > 0 and commits_after_deadline == 0:
        print("First commit was before the due date: +0pts")
        return True
    elif commits_before_deadline > 0 and commits_after_deadline > 0:
        print("Late penalty applied: -0.5pts")
        score -= 0.5
        return True
    elif commits_before_deadline == 0 and commits_after_deadline > 0:
        print("First commit was after deadline: No credit, see Dr. Gazzillo for questions and concerns")
        score = 0
        return False

def run_command(command, cwd=None):
    try:
        # Run the command and capture output in binary mode to manually handle decoding
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True)
        
        # Strict UTF-8 decoding, replacing invalid characters if any
        stdout = result.stdout.decode('utf-8', errors='replace')  # Replace invalid characters
        stderr = result.stderr.decode('utf-8', errors='replace')  # Replace invalid characters

        # Print the appropriate output based on success or failure
        if result.returncode == 0 or result.returncode == 1:
          print(f"Command succeeded: {command}")
          print(stdout)
        else:
          print(f"Command failed: {command}")
          print(stderr)

        # Return success/failure and the captured stdout
        return (result.returncode == 0 or result.returncode == 1), stdout  # Return the output
    except Exception as e:
        print(f"Error running command {command}: {e}")
        return False, ""

def main():
    global score
    total_scores = 0
    
    if len(sys.argv) > 2:
      nid = sys.argv[1]
      testcase_names = sys.argv[2:]
      
      repo_url = f"gitolite3@eustis3.eecs.ucf.edu:cop3402/{nid}/myls"
      clone_directory = "myls_new"
      
      # Remove existing directory if it exists
      if os.path.exists(clone_directory):
          shutil.rmtree(clone_directory)

      # Clone the repository
      cmd = f"git clone {repo_url} {clone_directory}"
      success, _ = run_command(cmd)
      if not success:
          # If cloning failed, give a grade of 0 for this student
          print(f"Failed to clone repository for NID {nid}.")
          return

      # Check the cloned directory
      run_command(f"ls {clone_directory}")

      # Run the grading function
      score = grade_repo(nid, clone_directory, testcase_names)
      return score
    else:
      print("Usage: python myls_grading_script.py <NID> public_testcases private_testcases")
      sys.exit(1)

      
if __name__ == "__main__":
    main()
