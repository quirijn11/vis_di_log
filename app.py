import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import visualize
import pandas as pd

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

name, authentication_status, username = authenticator.login()
if st.session_state["authentication_status"]:
    authenticator.logout('Logout', 'main')
    st.write(f'Welcome *{st.session_state["name"]}*')
    file = st.file_uploader("Upload Ship Report")
    if file:
        filtered_df = visualize.UploadSailReport(file).upload()
        print(filtered_df)
        min_date = filtered_df['Start'].iloc[0].date()
        max_date = (filtered_df['Einde'].iloc[-1] - pd.DateOffset(days=7)).date()
        selected_range = st.slider(
            "Select the start date of the week to visualize:",
            min_value=min_date,
            max_value=max_date,
            value=min_date,
            format="DD-MM-YYYY"  # Optional: specify the format of the date
        )

        st.plotly_chart(visualize.VizualizationPlanning(filtered_df).calls_gantt_chart(selected_range),
                        use_container_width=True)
elif not st.session_state["authentication_status"]:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')
