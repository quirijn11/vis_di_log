from datetime import timedelta

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
       This Cofano dashboard provides an overview of ship activities based on the uploaded ship reports.
       **In the sidebar on the left**, you can upload one or multiple ship reports in Excel format (from Cofano BOS)."
       """)

    st.divider()

    st.sidebar.markdown("## Upload Ship Report(s)")
    files = st.sidebar.file_uploader("Upload one or more Ship Report(s)",
                                     accept_multiple_files=True,
                                     help="Upload Ship Report(s) in Excel format, extracted for Cofano BOS ship "
                                          "reports. Able to upload multiple files.")
    st.sidebar.divider()

    st.session_state['generate_dashboard'] = True
    st.session_state['files'] = True

    if st.session_state.generate_dashboard and st.session_state.files:
        filtered_df = visualize.UploadMultipleSailReports(files).upload()
        if filtered_df.empty:
            st.stop()
        st.session_state['filtered_df'] = filtered_df

        # Sidebar for configuration
        st.sidebar.markdown("## Configuration")

        st.sidebar.markdown("Select on which day your administrative week starts")
        start_of_week = st.sidebar.selectbox('Week starts on:',
                                         ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
                                         index=5)

        ship_config = utils.assign_default_value_as_contract_hours(filtered_df)
        st.sidebar.markdown("Enter the number of weekly contract hours for each ship")
        edited_ship_config = st.sidebar.data_editor(ship_config, hide_index=True)
        dict_ship_config = edited_ship_config.set_index('Schip')['Contracturen'].to_dict()

        st.sidebar.markdown("Filter on unsatisfactory weeks")
        f = st.sidebar.selectbox('Only show weeks where ship does not satisfy contract hours:', ('Yes', 'No'), index=1)
        st.sidebar.divider()
        filter_boolean = False
        if f == 'Yes':
            filter_boolean = True

        filtered_df = utils.split_rows_on_day_change(filtered_df)
        filtered_df = utils.split_dataframe_into_weeks(filtered_df, start_of_week)

        if not filter_boolean:
            filtered_df_selected_start_day = filtered_df[filtered_df['Start_Weekday'] == start_of_week]
            start_of_weeks = sorted(filtered_df_selected_start_day['Start_Date'].unique().tolist())
            start_of_weeks_with_weekday = {}
            for item in start_of_weeks:
                start_of_weeks_with_weekday[item.strftime('%A') + " " + str(item.strftime('%d-%m-%Y'))] = item
            min_date = list(start_of_weeks_with_weekday.keys())[0]

            st.header("Visualize Ship Report(s)")
            if len(start_of_weeks_with_weekday) > 1:
                selection = st.select_slider(
                    "Select the start date of the week to visualize:",
                    options=start_of_weeks_with_weekday,
                    value=min_date  # Optional: specify the format of the date
                )
            else:
                selection = list(start_of_weeks_with_weekday.keys())[0]

            start_end, options_as_dates = utils.get_required_rows(dict_ship_config, filtered_df, filter_boolean)

            converted_selection = start_of_weeks_with_weekday[selection]
            start = options_as_dates[converted_selection]
            end = start_end[start][0]

            tab1, tab2 = st.tabs(["Week overview", "Total overview"])
            with tab1:
                visualize.write_week_info(start, start_of_week, end)
                if len(dict_ship_config) <= 1:
                    for ship in dict_ship_config:
                        visualize.show_week_hours(filtered_df, ship, start, dict_ship_config)
                else:
                    visualize.show_week_hours_as_df(filtered_df, start, dict_ship_config, start_of_week)
            with tab2:
                start_of_weeks = []
                for key in start_of_weeks_with_weekday:
                    start_of_weeks.append(start_of_weeks_with_weekday[key])
                visualize.show_period_hours_as_df(filtered_df, dict_ship_config, start_of_week)

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
            start_end, options_as_dates = utils.get_required_rows(dict_ship_config, filtered_df, filter_boolean)
            start_of_weeks = sorted(filtered_df['Start_Date'].unique().tolist())
            start_of_weeks_with_weekday = {}
            for item in start_end:
                if item.strftime('%A') == start_of_week and item.date() in options_as_dates:
                    for el in start_end[item]:
                        ship = el['Ship']
                        start_of_weeks_with_weekday[start_of_week + " " + str(item.date().strftime('%d-%m-%Y')) + " - " + ship] = item.date()

            st.header("Visualize Ship Report(s)")
            selection = st.selectbox(
                "Select week to visualize:",
                options=start_of_weeks_with_weekday  # Optional: specify the format of the date
            )

            converted_selection = start_of_weeks_with_weekday[selection]
            start = options_as_dates[converted_selection]
            ship = selection.split(' - ', 1)[1]
            end = None
            for item in start_end:
                if item == start:
                    for el in start_end[item]:
                        if el['Ship'] == ship:
                            end = el['End']
            end_next_day = (end + timedelta(seconds=1)).date()

            tab1, tab2 = st.tabs(["Week overview", "Total overview"])
            with tab1:
                st.write("The selected week is for ship", ship, "and is from", str(start.date().strftime('%d-%m-%Y')), " to ", str(end_next_day.strftime('%d-%m-%Y')), ".")
                visualize.show_week_hours(filtered_df, ship, start, dict_ship_config)
            with tab2:
                start_of_weeks = []
                for key in start_of_weeks_with_weekday:
                    start_of_weeks.append(start_of_weeks_with_weekday[key])
                visualize.show_period_hours_as_df(filtered_df, dict_ship_config, start_of_week)

            tab1, tab2, tab3 = st.tabs(["Timeline", "Activity Time Per Day", "Average Activity Time"])
            with tab1:
                st.plotly_chart(
                    visualize.VisualisationPlanning(filtered_df).calls_gantt_chart(start, end, ship),
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
