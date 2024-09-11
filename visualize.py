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

class UploadSailReport():

    def __init__(self, file):
        self.barge = None
        self.file = file

    def upload(self):
        df = pd.read_excel(self.file)
        self.barge = df.iat[1, 1]
        df.columns = df.iloc[7]
        df = df.iloc[8:-2].reset_index(drop=True)
        # Step 1: Fill the empty values in the "Day" column with the last valid entry
        df['Niet-flexibel'] = df['Niet-flexibel'].fillna(method='ffill')
        df['Date'] = df['Niet-flexibel'].str.extract(r'\((\d{1,2}-\d{1,2})\)')

        # Step 2: Append "-2024" to the date (or use the current year)
        df['Date'] = df['Date'] + '-2024'
        print(df)
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

        return self.barge, df


class VizualisationPlanning():

    def __init__(self, df):
        self.df = df

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

        # Create Gantt chart
        fig = px.timeline(filtered_df, x_start='Start',
                          x_end='Einde',
                          y='Schip',
                          color='Van',
                          title='Barge Schedule Gantt Chart')
        fig.update_yaxes(categoryorder='total ascending')

        fig.update_layout(xaxis_title='Date',
                          yaxis_title='Barge Name')

        return fig