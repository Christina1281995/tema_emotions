# Aspect Based Emotion Labeling

## Getting Started
First install the dependencies using conda. The environment.yml file contains all the dependencies. To create the environment, run the following command in the root directory of the project.
``` conda env create -f environment.yml ```
This will create a conda environment called "stream-env". To activate the environment, run the following command.
``` conda activate stream-env ```

## Running the App
To run the app, run the following command.
``` streamlit run app.py ```
if that is not working, try the following command.
``` python -m streamlit run app.py```

## Using the App
There is a `config.json` file in which you can specify the experimental settings.
It contains a list of `users` which has the following fields:
- `id`: Unique id of the user
- `name`: Name of the user
- `data_path`: Path to the data file for the user

If you first open up the app than you have to tip in the user name which gets compared with the predefined users in the `config.json` file. If the user name is correct, the app will load the data file specified in the `config.json` file or if you turn of the predefined flag in the `config.json` file, you can specify the data file in the app by uploading it.

The data file should be a csv file laying in the `data` directory. The csv file should contain the following columns:
- `text`: The text to be labeled
- `Aspect Term`: The aspect term to be labeled
- `Sentiment`: The sentiment of the aspect term

The results are then stored in a csv file in the `results` directory. The name of the file is the user name. 
With that you can also pause and continue the labeling process. If you want to continue the labeling process, you have to tipp in the user name again and the app will load the results file and continue the labeling process from there. 

## TODO
- [ ] Add a button to go back after labeling a sentence

