import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import visualize
import utils

st.set_page_config(layout="wide")

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
    st.divider()

    st.session_state['generate_dashboard'] = True
    st.session_state['files'] = True

    if st.session_state.generate_dashboard and st.session_state.files:
        filtered_df = visualize.UploadMultipleSailReports(files).upload()
        if filtered_df.empty:
            st.stop()
        st.session_state['filtered_df'] = filtered_df

        col1, col2, col3 = st.columns(3)

        with col1:
            start_of_week = st.radio('Week starts on:',
                                     ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                                     index=5)

        with col2:
            ship_config = utils.assign_default_value_as_contract_hours(filtered_df)
            edited_ship_config = st.data_editor(ship_config, hide_index=True)
            dict_ship_config = edited_ship_config.set_index('Schip')['Contracturen'].to_dict()

        with col3:
            f = st.radio('Only show weeks where ship does not satisfy contract hours:', ['Yes', 'No'], index=1)
            filter_boolean = False
            if f == 'Yes':
                filter_boolean = True

        if not filter_boolean:
            filtered_df_selected_start_day = st.session_state.filtered_df[
                st.session_state.filtered_df['Start_Weekday'] == start_of_week]
            start_of_weeks = sorted(filtered_df_selected_start_day['Start_Date'].unique().tolist())
            start_of_weeks_with_weekday = {}
            for item in start_of_weeks:
                start_of_weeks_with_weekday[start_of_week + " " + str(item)] = item
            min_date = list(start_of_weeks_with_weekday.keys())[0]
            start = st.select_slider(
                "Select the start date of the week to visualize:",
                options=start_of_weeks_with_weekday,
                value=min_date  # Optional: specify the format of the date
            )
            start = start_of_weeks_with_weekday[start]

            filtered_df = utils.split_dataframe_into_weeks(filtered_df, start_of_week)
            filtered_df = utils.split_rows_on_day_change(filtered_df)

            start_end, options_as_dates = utils.get_required_rows(dict_ship_config, filtered_df, filter_boolean)
            start = options_as_dates[start]
            end = start_end[start][0]
            visualize.write_week_info(start, start_of_week, end)

            for ship in dict_ship_config:
                visualize.show_week_hours(filtered_df, ship, start, dict_ship_config)

            tab1, tab2, tab3 = st.tabs(["Timeline", "Activity Time Per Day", "Average Activity Time"])
            with tab1:
                st.plotly_chart(
                    visualize.VisualisationPlanning(filtered_df).calls_gantt_chart(start, end),
                    use_container_width=True)
            with tab2:
                st.plotly_chart(
                    visualize.VisualisationPlanning(filtered_df).activity_line_chart(start),
                    use_container_width=True)
            with tab3:
                st.plotly_chart(visualize.VisualisationPlanning(filtered_df).activity_trend())
        else:
            filtered_df = utils.split_dataframe_into_weeks(filtered_df, start_of_week)
            filtered_df = utils.split_rows_on_day_change(filtered_df)

            start_end, options_as_dates = utils.get_required_rows(dict_ship_config, filtered_df, filter_boolean)

            st.divider()
            start = st.selectbox(
                "Select week to visualize:",
                options=sorted(list(options_as_dates.keys()))  # Optional: specify the format of the date
            )
            start = options_as_dates[start]
            end = start_end[start][0]
            ship = start_end[start][1]
            st.divider()
            st.write("The selected week is for ship", ship, "and is from", start, "to", end)
            visualize.show_week_hours(filtered_df, ship, start, dict_ship_config)
            tab1, tab2, tab3 = st.tabs(["Timeline", "Activity Time Per Day", "Average Activity Time"])
            with tab1:
                st.plotly_chart(
                    visualize.VisualisationPlanning(st.session_state.filtered_df).calls_gantt_chart(start, end, ship),
                    use_container_width=True)
            with tab2:
                st.plotly_chart(
                    visualize.VisualisationPlanning(filtered_df).activity_line_chart(start),
                    use_container_width=True)
            with tab3:
                st.plotly_chart(visualize.VisualisationPlanning(filtered_df).activity_trend())
            st.divider()

    elif not st.session_state["authentication_status"]:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')

# Footer with logo
