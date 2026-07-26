import subprocess
import os


def download(url, output_dir):

    os.makedirs(
        output_dir,
        exist_ok=True
    )


    command = [
        "gallery-dl",
        "-d",
        output_dir,
        url
    ]


    print(
        "Running:",
        " ".join(command)
    )


    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )


    if result.returncode != 0:

        print(
            "gallery-dl failed:"
        )

        print(
            result.stderr
        )

        return []


    files = []


    for root, dirs, filenames in os.walk(output_dir):

        for filename in filenames:

            files.append(
                os.path.join(
                    root,
                    filename
                )
            )


    return files
