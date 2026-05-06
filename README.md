# Introduction

## Calorie Tracker

A web-based calorie tracking application that allows users to search for foods, log meals, and analyze dietary intake.

# Technical Architecture

<img width="960" height="540" alt="CS 222 Final Presentation" src="https://github.com/user-attachments/assets/733fdcb5-1f00-403c-a698-f62e89852e89" />

# Environment Setup

## Initializing Virtual Environment

First, navigate to the project's source directory and create the enviornment by executing:

```
python3 -m venv .venv
```

Then activate the environment.

**Mac/Linux:**
```
source .venv/bin/activate
```

**Windows:**
```
.venv/Scripts/activate
```

## Package Installation

To install required packages, run:

```
pip install -r requirements.txt
```

## Setting API Keys

Before running the project, create a `.env` file in the root project directory. API keys must be set in `.env`. An example `.env` file is provided below:

```
FDC_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

The `FDC_API_KEY` is used when querying nutritional information from the USDA FoodData Central API. The `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are used to access the project's backend database.

Get an FDC API key here: https://fdc.nal.usda.gov/api-guide

# Project Instructions

To run the project, execute:

```
python3 main.py
```

The following should print on a successful launch:

```
 * Serving Flask app 'ui.ui'
 * Running on http://{IP}:{PORT}
```

Note that the project's virtual environment must be activated whenever running the project.

# Group Members
Artem Khaiet - Code integration, Search Result Deduplication, Goal Tracking, API Integration

Leo Penn - UI, Database Design

Martin Gospodinov - User Auth, Cloud Storage

Yassir Atlas - UI, Record Management 
