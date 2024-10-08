import streamlit as st
import plotly.express as px
import pandas as pd
import utils


def write_week_info(start, start_of_week, end):
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    if weekdays[start.weekday()] is not start_of_week:
        st.write("The selected week is from: ", start, " to ", end, ". Note: this month did not start on a",
                 start_of_week, ", therefore the first week of this month is not 7 days long.")
    else:
        st.write("The selected week is from: ", start, " to ", end, ".")


def show_week_hours(df, ship, start, ship_config):
    filtered_df = df[df['Schip'] == ship]
    sailing_time = filtered_df[filtered_df['Start'] == start]['Vaaruren_week']
    waiting_time = filtered_df[filtered_df['Start'] == start]['Wachttijd_week']
    terminal_time = filtered_df[filtered_df['Start'] == start]['Laad/Lostijd_week']
    contract_time = filtered_df[filtered_df['Start'] == start]['Tijd onder contract'].values[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sailing hours", round(sailing_time, 1))
    col2.metric("Waiting hours", round(waiting_time, 1))
    col3.metric("(Un)load hours", round(terminal_time, 1))
    col4.metric("Total hours", round(contract_time, 1), round(contract_time - ship_config[ship], 1))


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
        filtered_df = self.df[(self.df['Start'] >= start_date) & (self.df['Einde'] <= end_date)]
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
