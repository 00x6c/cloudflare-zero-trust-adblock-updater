# cf-zt-oisd-sync

This program downloads the official `OISD small` list and adds its domains to Cloudflare Zero Trust Gateway as reusable DOMAIN lists. It then creates a DNS Gateway rule that blocks those domains.

The program does not modify existing Cloudflare policies unless they were created by this program.

## Quickest path

If you want it to "just work", the overall flow is:

1. Open the project folder in a terminal.
2. Install Python and the dependencies.
3. Run `python run.py`.
4. Choose option `1` to create `.env`.
5. Choose option `2` to check the connection.
6. Choose option `3` to review the plan without making changes.
7. If the plan looks good, choose option `4`.
8. For later updates, run `python run.py` again and choose option `4`.

You can run the commands below in order.

## Install dependencies

In the project folder, run:

```bash
python3 -m pip install -e .
```

In Windows PowerShell, this usually works:

```powershell
python -m pip install -e .
```

## Easiest launch through the menu

After installing the dependencies, run:

```bash
python run.py
```

In WSL/Ubuntu, the command may be named `python3`:

```bash
python3 run.py
```

You will see a menu:

```text
1. Initial setup (.env)
2. Check Cloudflare and OISD connection
3. Dry-run: show plan without changes
4. Create or update lists and blocking rule
5. Show status
6. Delete created objects
7. Diagnose problems
8. Language / Язык
0. Exit
```

Enter the option number and press `Enter`. For example, the usual first-run sequence is:

```text
1 -> 2 -> 3 -> 4 -> 5
```

That means: configure, check, review the plan, apply it, then check the status.

If the program is installed as a CLI command, you can open the same menu with:

```bash
cf-zt-oisd-sync menu
```

## Which folder to open

Open the project folder itself:

```text
C:\Users\MAESTRO\Downloads\cloudflare zero trust adblock updater
```

If you work in WSL/Linux, the same path looks like this:

```text
/mnt/c/Users/MAESTRO/Downloads/cloudflare zero trust adblock updater
```

This folder should contain:

```text
README.md
pyproject.toml
.env.example
cf_zt_oisd_sync/
tests/
```

## How to open the folder

Any of these are fine:

- Windows Terminal;
- PowerShell;
- Ubuntu/WSL terminal;
- VS Code: `File -> Open Folder`, then `Terminal -> New Terminal`.

If you are not sure, the easiest option is to open VS Code, choose the project folder, and open the built-in terminal.

## How to enter the project folder

In WSL/Ubuntu:

```bash
cd "/mnt/c/Users/MAESTRO/Downloads/cloudflare zero trust adblock updater"
```

In PowerShell:

```powershell
cd "C:\Users\MAESTRO\Downloads\cloudflare zero trust adblock updater"
```

## Install Python

Check whether Python is installed:

```bash
python3 --version
```

Or in Windows PowerShell:

```powershell
py --version
```

Python 3.11 or newer is required.

If Python is not installed, install it from the official website:

```text
https://www.python.org/downloads/
```

On Windows, enable the `Add python.exe to PATH` checkbox during installation.

## Install dependencies

### Option A: WSL/Ubuntu

First install `pip` and the virtual environment module:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv
```

Then run this in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

After `source .venv/bin/activate`, `(.venv)` usually appears at the start of the terminal prompt. This is normal: it means a separate Python environment for this project is active.

### Option B: Windows PowerShell

Run this in the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
```

If PowerShell does not allow `.venv` activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try again:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Configure Cloudflare

The program needs two values:

- `CLOUDFLARE_ACCOUNT_ID`;
- `CLOUDFLARE_API_TOKEN`.

### Where to find the Account ID

1. Open the Cloudflare dashboard.
2. Select the account you want to use.
3. `Account ID` is usually visible in the right sidebar or in the account/profile section.
4. Copy the full value.

### How to create an API token

1. Open the Cloudflare dashboard.
2. Go to `My Profile -> API Tokens`.
3. Click `Create Token`.
4. Create a token with permissions for Cloudflare Zero Trust Gateway Lists and Gateway Rules.
5. Copy the token immediately after it is created.

Cloudflare shows the token only once. If you close the page without copying it, it is usually easier to create a new one.

## Create `.env`

The easiest way:

```bash
cf-zt-oisd-sync setup
```

The program will ask:

```text
Enter Cloudflare Account ID:
Enter Cloudflare API Token:
OISD small source [https://small.oisd.nl]:
List prefix [oisd-small-auto]:
Rule name [OISD Small Auto Block]:
List chunk size [1000]:
```

For most questions, you can press `Enter` and keep the default values. You only need to enter `Account ID` and `API Token` manually.

After that, a `.env` file will appear in the folder. This is a regular text file with settings. You can open it in VS Code or Notepad, but do not publish it online: it contains a secret API token.

## Check before running

Run:

```bash
cf-zt-oisd-sync check
```

If everything is good, you will see lines with `[OK]`.

If you see an error about the token or permissions, check:

- whether `CLOUDFLARE_API_TOKEN` was pasted correctly;
- whether `CLOUDFLARE_ACCOUNT_ID` was pasted correctly;
- whether the token has permissions for Gateway Lists and Gateway Rules.

## Safe preview

Before creating real objects, run:

```bash
cf-zt-oisd-sync dry-run
```

This command does not change anything in Cloudflare. It only shows how many lists will be created and which rule will appear.

## First real run

If `dry-run` looks good:

```bash
cf-zt-oisd-sync init
```

The program will ask for confirmation. After you confirm, it will create:

- several Cloudflare DOMAIN lists;
- one DNS Gateway rule;
- a local state file, `.cf-zt-oisd-state.json`.

During creation, you will see progress indicators for the Cloudflare lists and the DNS Gateway rule. If there are many lists, that is normal: Cloudflare accepts them in chunks.

The state file lets the program remember which objects it created. You do not need to edit it manually.

## How to check that everything works

Run:

```bash
cf-zt-oisd-sync status
```

A good result looks roughly like this:

```text
[OK] Local state matches Cloudflare
```

You can also open the Cloudflare Zero Trust dashboard and check Gateway lists/rules manually.

## How to update the list

Normal update:

```bash
cf-zt-oisd-sync update
```

Automatic update without questions:

```bash
cf-zt-oisd-sync update --yes
```

During updates, the program also shows progress: one indicator for the lists and one for the blocking rule.

## How to delete everything created by the program

Interactively:

```bash
cf-zt-oisd-sync delete
```

The program will ask you to type:

```text
DELETE
```

Automatically, without a question:

```bash
cf-zt-oisd-sync delete --yes
```

Only this program's managed objects are deleted: lists with the configured prefix, objects from the state file, and objects marked with `Managed by cf-zt-oisd-sync`.

## What to run every day

For regular updates, use:

```bash
cf-zt-oisd-sync update --yes
```

### Windows Task Scheduler

Command for the scheduler:

```powershell
python -m cf_zt_oisd_sync.cli update --yes
```

The working folder must be the project folder:

```text
C:\Users\MAESTRO\Downloads\cloudflare zero trust adblock updater
```

### Linux cron

Example for running every day at 04:00:

```bash
0 4 * * * cd "/mnt/c/Users/MAESTRO/Downloads/cloudflare zero trust adblock updater" && . .venv/bin/activate && cf-zt-oisd-sync update --yes
```

## FAQ

### Which file should I open?

Open `README.md` for instructions.

Open `.env` for settings.

Open `.cf-zt-oisd-state.json` to inspect the state, but you usually do not need to edit it.

### How should I open `.env`?

VS Code, Notepad, Notepad++, or any text editor will work. VS Code is usually the most convenient.

### Why is `.env` not visible?

Files that start with a dot are sometimes treated as hidden files. They are usually visible in VS Code. In Windows Explorer, enable hidden files.

### What if the `cf-zt-oisd-sync` command is not found?

Most likely, the virtual environment is not active.

In WSL/Ubuntu:

```bash
source .venv/bin/activate
```

In PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then try again:

```bash
cf-zt-oisd-sync --help
```

### What if I get `python3: No module named pip`?

In WSL/Ubuntu, install `pip`:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv
```

Then repeat the dependency installation.

### What if Cloudflare returned `403 Forbidden`?

This almost always means the API token does not have the required permissions. Create or update a token with access to Zero Trust Gateway Lists and Gateway Rules.

### What if I am afraid of breaking something?

Start with:

```bash
cf-zt-oisd-sync dry-run
```

This command does not change anything. It only shows the plan.

### Can I change `CHUNK_SIZE`?

Usually, leave it at `1000`. This is a safe value for Standard/free-like Cloudflare plans.

### What is the state file?

It is the `.cf-zt-oisd-state.json` file. The program writes the IDs of the created Cloudflare lists and rule there. That is how it knows what to update and what to delete.

### Can I delete the state file?

It is better not to delete it. If it disappears, run:

```bash
cf-zt-oisd-sync doctor
```

### How do I know the program will not delete anything extra?

The `delete` command only looks for objects that appear to have been created by this program:

- they are listed in the state file;
- or they have the configured prefix;
- or their description contains `Managed by cf-zt-oisd-sync`.

## Command reference

```bash
cf-zt-oisd-sync --help
cf-zt-oisd-sync setup
cf-zt-oisd-sync check
cf-zt-oisd-sync dry-run
cf-zt-oisd-sync init
cf-zt-oisd-sync update
cf-zt-oisd-sync status
cf-zt-oisd-sync delete
cf-zt-oisd-sync doctor
```

## Developer checks

If dev dependencies are installed:

```bash
pytest
```
