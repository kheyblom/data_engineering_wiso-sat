We need to build a codebase that will prepare zarr stores for TROPOMI HDO L2 data products.

Raw data is located here: @/glade/u/home/kheyblom/scratch/data/wiso-sat/raw/TROPOMI/tropomi.grid.surfsara.nl/
We will be creating one zarr store per variable covering every day in the total database (changed from one store per day, 2026-10-14). Level 2 data only.

# 1. init CLAUDE.md for the codebase [COMPLETED 2026-10-13]
Create a CLAUDE.md in this directory.

# 2. init a git repo [COMPLETED 2026-10-13]
Check if a repo already exists for @./data_engineering_wiso-sat. If the repo does not exist, initalize a github repo and connect to the remote (see general notes).

# 3. Collaborate to update style guides
The data is different the previous data engineering codebases that have been built. Previous projects have only dealt with gridded datasets. This is a level 2 satellite retrieval product. Thus, we will likely need to work on creating the standards that will go into updating the style guide.

This data also uses variables that are not in the style guide. We will work together to add all of the new variables that we need to.

# 4. Plan and build the codebase
I want you to build the codebase. Design the codebase to be consistent with the other data_engineering codebases (see general notes).

## Design notes:
- The environment is already created. See @../pyproject.toml.
- Make sure to follow the style guides outlined in @/glade/u/home/kheyblom/work/style_guides.
- Follow the structure and style in the past data_engineering products: @/glade/u/home/kheyblom/work/data_engineering. Make sure that we are consistent with each of those.
- We will only produce zarr stores for a subset of the available variables. The config needs to be flexible to specify which variables we want to run the stores for during a production run.


# 5. Create a testing plan for the codebase
Develop a plan to test this codebase so that we know that it works before we move to production runs.

# 6. Production runs: create the final prooduct zarr stores.


# General notes:
- all file paths are relative to this TASKS.md file.
- the git remote is: https://github.com/kheyblom/data_engineering_wiso-sat.git
- ensure to always use proper git version controlling as changes are made
- use and update a CLAUDE.md that will take this information and effectively and efficiently handle this project. Don't be overly verbose. Keep the CLAUDE.md minimal and clean.
- use information learned in each of the directories in: @/glade/u/home/kheyblom/work/data_engineering and add to this project's CLAUDE.md. Each directory contains a codebase for creating zarr stores for our data lake.
- it is always important to minimize compute costs on derecho. we have a finite allocation and we need to managing our usage.
- keep notes on your current working state. you may lose connection to the HPC system or I may need to start new sessions, so I need you to be able to easily pick up where you left off. Create and use the file STATE.md.
- additional tasks may come up that need to occur between the above tasks. this task list can be flexible, but if substantial changes are need, I need to approve them.
- mark tasks as completed when they are completed