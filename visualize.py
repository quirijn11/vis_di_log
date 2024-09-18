from cProfile import label

import streamlit as st
import plotly.express as px
import pandas as pd
import re


def adjust_datetime(row):
    # Ensure that the value is a string before applying regex
    time_value = str(row['Einde']) if pd.notna(row['Einde']) else ''

    # If the "Time" contains a date in parentheses, extract it and adjust the date
    match = re.search(r'\((\d{1,2} \w{3})\)', time_value)
    if match:
        # Extract the next-day date (e.g., "01 Aug")
        next_day_str = match.group(1)
        next_day = pd.to_datetime(next_day_str + ' 2024', format='%d %b %Y')  # Assuming the year 2024
        # Remove the "(01 Aug)" part from the Time column to extract the time
        time_part = time_value.split(' ')[0]
        return pd.to_datetime(next_day.strftime('%d-%m-%Y') + ' ' + time_part, format='%d-%m-%Y %H:%M')
    else:
        # If no next-day indication, combine the current row's date and time
        return pd.to_datetime(row['Date'] + ' ' + time_value, format='%d-%m-%Y %H:%M')


def convert_to_minutes(time_str):
    """ Convert time string in H:MM format to total minutes. """
    if pd.isna(time_str):
        return None

    # Split the time string into hours and minutes
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])

    # Calculate total minutes
    total_minutes = hours * 60 + minutes
    return total_minutes


# Function to update "Van" and "Tot" based on conditions
def update_van_tot(row):
    if row['Rusttijd'] > 0:
        row['Van'] = 'Rust'
        row['Tot'] = ''
    elif row['Vaaruren'] > 0:
        row['Van'] = 'Varen'
        row['Tot'] = ''
    elif row['Wachttijd'] > 0:
        row['Van'] = 'Wachten'
        row['Tot'] = ''

    return row


class UploadSailReport:

    def __init__(self, file):
        self.barge = None
        self.file = file

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
        df['Einde'] = df.apply(adjust_datetime, axis=1)

        for column in ['Vaaruren', 'Wachttijd', 'Rusttijd', 'Laad/Lostijd']:
            df[column] = df[column].apply(convert_to_minutes)
            df[column] = df[column].fillna(0)


        # Drop the specified columns
        df = df.drop(columns=['Niet-flexibel', 'Date', 'Opmerkingen'])
        df = df.fillna('')
        df['Schip'] = self.barge

        # Apply the function to each row
        df = df.apply(update_van_tot, axis=1)

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

        return self.df


class VisualisationPlanning:

    def __init__(self, df):
        self.df = df

    import pandas as pd
    import plotly.express as px

    def calls_gantt_chart(self, start_date):
        """
        Description: This visualization shows the calls in a Gantt chart for a specific week.
        Purpose: Understand the calls and their duration within a given week.
        Type: Gantt chart
        Values used: Call start time, Call end time
        Title: Calls Gantt Chart
        X-axis: Time
        Y-axis: Calls
        :param start_date: The Saturday of the week to filter data. Should be in 'YYYY-MM-DD' format.
        :return: Calls Gantt chart in streamlit app
        """

        # Convert start_date to datetime and calculate the end of the week (Friday)
        start_date = pd.to_datetime(start_date)
        end_date = start_date + pd.DateOffset(days=6)

        # Filter DataFrame for the specific week
        filtered_df = self.df[(self.df['Start'] >= start_date) & (self.df['Einde'] <= end_date)]

        # Define a color map for the 'Van' categories
        color_map = {'Varen': 'green', 'Wachten': 'red', 'Rust': 'brown'}

        filtered_df["Activiteit"] = filtered_df["Van"].apply(lambda x: x if x in color_map else "Terminal")

        # Create Gantt chart with 'Van' column as color, and apply the color map
        fig = px.timeline(filtered_df,
                          x_start='Start',
                          x_end='Einde',
                          y='Schip',
                          color='Activiteit',  # Use the 'Van' column for coloring
                          text='Van',  # Display the 'Van' column inside the blocks
                          title='Barge Schedule Gantt Chart',
                          color_discrete_map=color_map)  # Apply consistent color mapping

        # Ensure the y-axis is ordered by category
        fig.update_yaxes(categoryorder='total ascending')

        # Update the layout for axis titles and hide the legend
        fig.update_layout(xaxis_title='Date',
                          yaxis_title='Barge Name',
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
        _filtered_df = self.df[(self.df['Start'] >= start_date) & (self.df['Einde'] <= end_date)]

        # Extract day from Start time
        _filtered_df['Dag'] = _filtered_df['Start'].dt.date

        _filtered_df = _filtered_df[["Vaaruren", "Wachttijd", "Rusttijd", "Laad/Lostijd", "Schip", "Dag"]]
        _filtered_df.rename(columns={"Vaaruren": "Varen", "Wachttijd": "Wachten", "Rusttijd": "Rust", "Laad/Lostijd": "Terminal"}, inplace=True)

        # Define a color map for the 'Van' categories
        color_map = {'Varen': 'green', 'Wachten': 'red', 'Rust': 'brown', 'Terminal': 'pink'}

        # Group by ship, day, and activity, and calculate average time per activity per day
        grouped_df = _filtered_df.groupby(['Schip', 'Dag'], as_index=False).mean()

        # Create the line chart
        fig = px.bar(grouped_df, x='Dag', y=['Varen', 'Wachten', 'Rust', 'Terminal'],
                     title='Average Activity Time Per Ship Per Day',
                     labels={'value': 'Average Time (minutes)', 'Day': 'Date'},
                     color_discrete_map=color_map,
                     facet_col='Schip') # Separate the chart by ship)

        return fig

    def activity_trend(self):
        # Convert Start and Einde columns to datetime

        _filtered_df = self.df.copy()
        # Extract day from Start time
        _filtered_df['Dag'] = _filtered_df['Start'].dt.date

        # Reindex, set dag as index and sort by index
        _filtered_df = _filtered_df.set_index('Dag').sort_index()
        _filtered_df = _filtered_df[["Vaaruren", "Wachttijd", "Rusttijd", "Laad/Lostijd", "Schip"]]
        _filtered_df.rename(columns={"Vaaruren": "Varen", "Wachttijd": "Wachten", "Rusttijd": "Rust", "Laad/Lostijd": "Terminal"}, inplace=True)

        # Define a color map for the 'Van' categories
        color_map = {'Varen': 'green', 'Wachten': 'red', 'Rust': 'brown', 'Terminal': 'pink'}

        # create rolling of 7 days for each ship and activity and calculate the mean
        _filtered_df = _filtered_df.groupby(['Schip']).rolling(window=7).mean().reset_index()


        fig = px.line(_filtered_df, x='Dag', y=['Varen', 'Wachten', 'Rust', 'Terminal'],
                     title='Average Activity Time Per Ship Per Day',
                     labels={'value': 'Average Time (minutes)', 'Day': 'Date'},
                     color_discrete_map=color_map,
                      line_dash='Schip')

        return fig

