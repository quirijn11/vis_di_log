import streamlit as st
import plotly.express as px
import pandas as pd
import utils
from datetime import timedelta

def write_week_info(start, start_of_week, end):
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    end_next_day = (end + timedelta(seconds=1)).date()
    if weekdays[start.weekday()] is not start_of_week:
        st.write("The selected week is from: ", str(start.date().strftime('%d-%m-%Y')), " to ",
                 str(end_next_day.strftime('%d-%m-%Y')), ". Note: this file did not start on a",
                 start_of_week, ", therefore the first week of this file is not 7 days long.")
    else:
        st.write("The selected week is from: ", str(start.date().strftime('%d-%m-%Y')), " to ",
                 str(end_next_day.strftime('%d-%m-%Y')), ".")


def show_week_hours(df, ship, start, ship_config):
    filtered_df = df[df['Schip'] == ship]
    sailing_time = round(filtered_df[filtered_df['Start'] == start]['Vaaruren_week'], 1)
    waiting_time = round(filtered_df[filtered_df['Start'] == start]['Wachttijd_week'], 1)
    terminal_time = round(filtered_df[filtered_df['Start'] == start]['Laad/Lostijd_week'], 1)
    contract_time = round(filtered_df[filtered_df['Start'] == start]['Tijd onder contract'].values[0], 1)
    container = st.container(border=True)
    if len(ship_config) > 1:
        col1, col2, col3, col4, col5 = container.columns(5)
        col1.markdown(f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 85px;">
                <div>
                    <strong>{ship}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
        col2.metric("Sailing hours", sailing_time)
        col3.metric("Waiting hours", waiting_time)
        col4.metric("(Un)load hours", terminal_time)
        col5.metric("Total hours", contract_time, round(contract_time - ship_config[ship], 1))
    else:
        col1, col2, col3, col4 = container.columns(4)
        col1.metric("Sailing hours", sailing_time)
        col2.metric("Waiting hours", waiting_time)
        col3.metric("(Un)load hours", terminal_time)
        col4.metric("Total hours", contract_time, round(contract_time - ship_config[ship], 1))


def show_week_hours_as_df(df, start, ship_config):
    columns = ['Ship', 'Sailing hours', 'Waiting hours', '(Un)load hours', 'Total hours']
    df_to_show = pd.DataFrame(columns=columns)
    for ship in ship_config:
        filtered_df = df[df['Schip'] == ship]
        if start.date() in filtered_df['Start_Date'].values:
            sailing_time = round(filtered_df[filtered_df['Start'] == start]['Vaaruren_week'], 1)
            waiting_time = round(filtered_df[filtered_df['Start'] == start]['Wachttijd_week'], 1)
            terminal_time = round(filtered_df[filtered_df['Start'] == start]['Laad/Lostijd_week'], 1)
            contract_time = round(filtered_df[filtered_df['Start'] == start]['Tijd onder contract'].values[0], 1)
            new_row = {'Ship': ship, 'Sailing hours': sailing_time, 'Waiting hours': waiting_time,
                       '(Un)load hours': terminal_time, 'Total hours': contract_time}
            entry = pd.DataFrame.from_dict(new_row)
            df_to_show = pd.concat([df_to_show, entry], ignore_index=True)

    # Set display format for floats
    pd.options.display.float_format = '{:.1f}'.format  # Adjust the number of decimal places as needed

    # Apply the style only to the 'Total hours' column based on the corresponding Threshold
    styled_df = df_to_show.style.apply(lambda row: highlight_rows(row, ship_config, df_to_show.columns), axis=1)

    # Display the styled DataFrame in Streamlit
    st.dataframe(styled_df, width=1400)


# Function to highlight Total hours based on the corresponding Threshold value
def highlight_total_hours(total_hours, threshold):
    return 'background-color: red' if total_hours < threshold else ''


# Create a function to apply styles only to the "Total hours" column
def highlight_rows(row, ship_config, columns):
    styles = [''] * len(row)  # Create a list with the same length as the row, initialized with empty strings
    total_hours = row['Total hours']
    ship_name = row['Ship']

    # Highlight only the 'Total hours' cell
    total_hours_index = columns.get_loc('Total hours')
    styles[total_hours_index] = highlight_total_hours(total_hours, ship_config[ship_name])

    return styles


class UploadSailReport:

    def __init__(self, file):
        self.barge = None
        self.file = file

    # Function to calculate the sum until conditions are met

    def upload(self):
        df = pd.read_excel(self.file)
        self.barge = df.iat[1, 1]
        df.columns = df.iloc[7]
        df = df.iloc[8:-2].reset_index(drop=True)
        # Step 1: Fill the empty values in the "Day" column with the last valid entry
        if 'Niet-flexibel' not in df.columns:
            df.rename(columns={'Dag': 'Niet-flexibel'}, inplace=True)

        df['Niet-flexibel'] = df['Niet-flexibel'].fillna(method='ffill')
        df['Date'] = df['Niet-flexibel'].str.extract(r'\((\d{1,2}-\d{1,2})\)')

        # Step 2: Append "-2024" to the date (or use the current year)
        df['Date'] = df['Date'] + '-2024'
        # Step 3: Combine the Date and Time columns
        df['Start'] = pd.to_datetime(df['Date'] + ' ' + df['Start'], format='%d-%m-%Y %H:%M')
        df['Einde'] = df.apply(utils.adjust_datetime, axis=1)

        for column in ['Vaaruren', 'Wachttijd', 'Rusttijd', 'Laad/Lostijd']:
            df[column] = df[column].apply(utils.convert_to_minutes)
            df[column] = df[column].fillna(0)

        # Drop the specified columns
        df = df.drop(columns=['Niet-flexibel', 'Date', 'Opmerkingen'])
        df = df.fillna('')

        df['Schip'] = self.barge

        df['Start_Date'] = df['Start'].dt.date
        df['Einde_Date'] = df['Einde'].dt.date

        df['Start_Weekday'] = df['Start'].dt.day_name()
        df['Einde_Weekday'] = df['Einde'].dt.day_name()

        # df = calculate_rolling_sums(df)

        # df['Valt onder contracturen'] = (df['Vaaruren_rolling_sum'] + df['Wachttijd_rolling_sum']
        #                                  + df['Laad/Lostijd_rolling_sum']) / 60

        # Apply the function to each row
        df = df.apply(utils.update_van_tot, axis=1)

        return df


class UploadMultipleSailReports(UploadSailReport):
    """
    This class offers the opportunity to upload multiple sail reports and combine them into a single DataFrame.

    """

    def __init__(self, files):
        self.files = files
        self.df = None

    def upload(self):

        if not self.files:
            return pd.DataFrame()

        dfs = []

        for file in self.files:
            df = UploadSailReport(file).upload()
            dfs.append(df)

        self.df = pd.concat(dfs)
        self.df = self.df.reset_index()

        return self.df


class VisualisationPlanning:

    def __init__(self, df):
        self.df = df

    def calls_gantt_chart(self, start_date, end_date, ship=None):
        """
        Description: This visualization shows the calls in a Gantt chart for a specific week.
        Purpose: Understand the calls and their duration within a given week.
        Type: Gantt chart
        Values used: Call start time, Call end time
        Title: Calls Gantt Chart
        X-axis: Time
        Y-axis: Calls
        :param start_date: The start date of the period shown in the chart.
        :param end_date: The end date of the period shown in the chart.
        :param ship: The ship corresponding to the data shown in the chart.
        :return: Calls Gantt chart in streamlit app
        """

        # Convert start_date to datetime and calculate the end of the week (Friday)
        start_date = pd.to_datetime(start_date)

        # Filter DataFrame for the specific week
        filtered_df = self.df[(self.df['Start_Date'] >= start_date.date()) & (self.df['Einde_Date'] <= end_date.date())]
        if ship is not None:
            filtered_df = filtered_df[filtered_df['Schip'] == ship]

        # Define a color map for the 'Van' categories
        color_map = {'Varen': 'green', 'Wachten': 'blue', 'Rust': 'brown', 'Terminal': 'pink'}

        filtered_df["Activiteit"] = filtered_df["Van"].apply(lambda x: x if x in color_map else "Terminal")

        # Create Gantt chart with 'Van' column as color, and apply the color map
        fig = px.timeline(filtered_df,
                          x_start='Start',
                          x_end='Einde',
                          y='Schip',
                          color='Activiteit',  # Use the 'Van' column for coloring
                          text='Van',  # Display the 'Van' column inside the blocks
                          title='Ship Timeline',
                          color_discrete_map=color_map,  # Apply consistent color mapping
                          category_orders={"Activiteit": ["Terminal", "Rust", "Varen", "Wachten"]})

        # Ensure the y-axis is ordered by category
        fig.update_yaxes(categoryorder='total ascending')

        # Update the layout for axis titles and hide the legend
        fig.update_layout(xaxis_title='Date',
                          yaxis_title='Ship Name',
                          showlegend=True,  # You can hide the legend if needed
                          legend_title='Activity')

        # Center the text inside the Gantt chart blocks
        fig.update_traces(textposition='inside')

        return fig

    def activity_line_chart(self, start_date):
        # Convert Start and Einde columns to datetime

        # Convert start_date to datetime and calculate the end of the week (Friday)
        start_date = pd.to_datetime(start_date)
        end_date = start_date + pd.DateOffset(days=6)

        # Filter DataFrame for the specific week
        _filtered_df = self.df[
            (self.df['Start_Date'] >= start_date.date()) & (self.df['Einde_Date'] <= end_date.date())
            ]
        _filtered_df = _filtered_df[["Vaaruren", "Wachttijd", "Rusttijd", "Laad/Lostijd", "Schip", "Start_Date"]]
        _filtered_df.rename(
            columns={"Vaaruren": "Varen", "Wachttijd": "Wachten", "Rusttijd": "Rust", "Laad/Lostijd": "Terminal"},
            inplace=True)

        # Define a color map for the 'Van' categories
        color_map = {'Varen': 'green', 'Wachten': 'blue', 'Rust': 'brown', 'Terminal': 'pink'}

        # Group by ship, day, and activity, and calculate average time per activity per day
        grouped_df = _filtered_df.groupby(['Schip', 'Start_Date'], as_index=False).sum()

        # Create the line chart
        fig = px.bar(grouped_df, x='Start_Date', y=['Varen', 'Wachten', 'Rust', 'Terminal'],
                     title='Total Activity Time Per Ship Per Day',
                     labels={'value': 'Time (minutes)', 'Day': 'Date'},
                     color_discrete_map=color_map,
                     category_orders={"variable": ["Terminal", "Rust", "Varen", "Wachten"]},
                     facet_col='Schip')  # Separate the chart by ship)

        return fig

    def activity_trend(self):
        # Convert Start and Einde columns to datetime

        _filtered_df = self.df.copy()
        # Extract day from Start time
        _filtered_df['Dag'] = _filtered_df['Start'].dt.date

        # Reindex, set dag as index and sort by index
        _filtered_df = _filtered_df.set_index('Dag').sort_index()
        _filtered_df = _filtered_df[["Vaaruren", "Wachttijd", "Rusttijd", "Laad/Lostijd", "Schip"]]
        _filtered_df.rename(
            columns={"Vaaruren": "Varen", "Wachttijd": "Wachten", "Rusttijd": "Rust", "Laad/Lostijd": "Terminal"},
            inplace=True)

        # Define a color map for the 'Van' categories
        color_map = {'Varen': 'green', 'Wachten': 'blue', 'Rust': 'brown', 'Terminal': 'pink'}

        # create rolling of 7 days for each ship and activity and calculate the mean
        _filtered_df = _filtered_df.groupby(['Schip']).rolling(window=7).mean().reset_index()

        fig = px.line(_filtered_df, x='Dag', y=['Varen', 'Wachten', 'Rust', 'Terminal'],
                      title='Average Activity Time Per Ship Per Day',
                      labels={'value': 'Average Time (minutes)', 'Day': 'Date'},
                      color_discrete_map=color_map,
                      category_orders={"variable": ["Terminal", "Rust", "Varen", "Wachten"]},
                      line_dash='Schip')

        return fig
