import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import visualize
import pandas as pd

st.markdown("""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: white;
        color: black;
        text-align: center;
        padding: 10px;
    }
    .footer img {
        height: 50px;
    }
    </style>
    <div class="footer">
        <p>Powered by <img src="https://nederlandvacature.nl/werkgever/logo/37021/" alt="Logo"></p>
    </div>
    """, unsafe_allow_html=True)

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

    # Header and description
    st.title("Ship Activity Dashboard")
    st.markdown("""
       This dashboard provides an overview of ship activities based on the uploaded ship reports.
       You can visualize the average time spent on various activities with a rolling window of 7 days.
       """)

    files = st.file_uploader("Upload one or more Ship Report(s)",
                             accept_multiple_files=True,
                             help="Upload Ship Report(s) in Excel format, extracted for Cofano BOS ship reports. "
                                  "Able to upload multiple files.")

    st.session_state['generate_dashboard'] = True
    st.session_state['files'] = True

    if st.session_state.generate_dashboard and st.session_state.files:
        filtered_df = visualize.UploadMultipleSailReports(files).upload()
        if filtered_df.empty:
            st.stop()
        st.session_state['filtered_df'] = filtered_df
        min_date = st.session_state.filtered_df['Start'].iloc[0].date()
        max_date = (st.session_state.filtered_df['Einde'].iloc[-1] - pd.DateOffset(days=7)).date()
        selected_range = st.slider(
            "Select the start date of the week to visualize:",
            min_value=min_date,
            max_value=max_date,
            value=min_date,
            format="DD-MM-YYYY"  # Optional: specify the format of the date
        )
        st.plotly_chart(visualize.VisualisationPlanning(st.session_state.filtered_df).calls_gantt_chart(selected_range),
                        use_container_width=True)

        st.plotly_chart(visualize.VisualisationPlanning(st.session_state.filtered_df).activity_line_chart(selected_range),
                        use_container_width=True)

        st.plotly_chart(visualize.VisualisationPlanning(st.session_state.filtered_df).activity_trend())


    elif not st.session_state["authentication_status"]:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')

# Footer with logo


