import streamlit as st
import os
import pandas as pd
import json
import re

@st.cache_data
def load_data(upload_obj):
    if upload_obj is None:
        return None
    try:
        df = pd.read_csv(upload_obj)
    except (ValueError, RuntimeError, TypeError, NameError):
        print("Unable to process your request.")
    return df

def save_results(df):
    output_filename = './results/results_' + str(st.session_state.user_id) + '.csv'
    if os.path.isfile(output_filename):
        df.to_csv(output_filename, mode='a', header=False, index=False, sep=';')
    else:
        print("File does not exist")
        df.to_csv(output_filename, header=True, index=False, sep=';')


# helper functions:
def increment_index():
    st.session_state["question_number"] += 1

def decrement_index():
    st.session_state["question_number"] -= 1


# load config file
with open('config.json') as f:
    config = json.load(f)

# create app 
st.title('Geo-Social Analytics: Aspect Based Emotion Labeling')

# set initial state
if "start" not in st.session_state:
    st.session_state["start"] = False

if "expander" not in st.session_state:
    st.session_state["expander"] = True

user_ids = [i["name"] for i in config["users"]]
if st.session_state["start"] == False:

    user_name = st.text_input('Please type in your user id')
    if user_name != '':
        st.write('User_id:', user_name)
        if user_name in user_ids:
            id_provided = user_name
            # check if the user is new or returning
            output_filename = './results/results_' + str(id_provided) + '.csv'
            results_frame = pd.DataFrame()
            if os.path.isfile(output_filename):
                results_frame = pd.read_csv(output_filename, sep=';')
                print("shape", results_frame)
            if results_frame.shape[0] > 0:
                last_row = results_frame.shape[0] - 1
                question_number = int(results_frame["q_num"][last_row]) + 1
            else:
                question_number = 0

            st.session_state["start"] = True
            # defining our Session State
            st.session_state["q_num"] = []
            st.session_state["emotions"] = []
            st.session_state.user_id = id_provided
            st.session_state.question_number = question_number
            st.button("Start Labeling")

        else:
            st.write('User_id not found')

else:

    if config["predefined"]:
        path = [j["data_path"] for j in config["users"] if j["name"] == st.session_state.user_id][-1]
        df = pd.read_csv(path)

    else:
        with st.expander("Upload data", expanded=st.session_state.expander):
            # load Data 
            uploaded_data = st.file_uploader("Csv file", type = ['.csv'])
            df = load_data(uploaded_data)
            st.info("Upload data")
            st.session_state.expander = False


    if df is not None:

        st.progress(st.session_state.question_number/df.shape[0])

        if st.session_state.question_number < df.shape[0]:
            # Sentence
            sentence = df["Sentence"][st.session_state.question_number]
            aspect_term = df["Aspect Terms"][st.session_state.question_number]
            sentiment = df["Sentiment"][st.session_state.question_number]

            # Highlight aspect term in the sentence
            sentence = re.sub(
                r"\b" + re.escape(aspect_term) + r"\b",  # exact match of the aspect term
                lambda match: f"<span style='color:red'>{match.group(0)}</span>",  # wrap in HTML span tag with red color
                sentence,
                flags=re.IGNORECASE
            )

            st.markdown(f"**Sentence:** {sentence}", unsafe_allow_html=True)
            st.markdown(f"**Aspect Term:** {aspect_term}")
            st.markdown(f"**Sentiment:** {sentiment}")

            form_key = "my_form"
            with st.form(key=form_key):
                options = [('Anger', 'Anger'), ('Sadness', 'Sadness'), ('Happiness', 'Happiness'), ('Fear', 'Fear'), ('None', 'None')]
                emotion = st.radio(
                    'Assign an emotion to the aspect phrase', 
                    options, 
                    index=4, 
                    format_func=lambda x: x[1])

                if st.form_submit_button("Submit", on_click=increment_index):
                    data = {"q_num": st.session_state.question_number, "emotions": emotion}
                    save_results(pd.DataFrame(data, columns=["q_num", "emotions"]))
                    increment_index()  # Increment the question number for the next sentence

                # if st.form_submit_button("Back"):
                #         decrement_index()  # Decrement the question number for the previous sentence
                #         increment_index()  # Increment the question number to display the previous sentence again

            st.write("---")
            # st.button("Next", on_click=increment_index)

        else:
            st.markdown("End of data.")
