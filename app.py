import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import visualize

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
        barge, filtered_df = visualize.UploadSailReport(file).upload()
        st.plotly_chart(visualize.VizualisationPlanning(filtered_df).calls_gantt_chart('2024-08-17'),
                        use_container_width=True)
elif not st.session_state["authentication_status"]:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')

