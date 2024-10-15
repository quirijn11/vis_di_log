import math

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


# Function to split the DataFrame into weeks
def split_dataframe_into_weeks(df, day='Saturday'):
    # Split the DataFrame into a dictionary of DataFrames based on unique values in 'Ship'
    grouped_dfs = {ship: group for ship, group in df.groupby('Schip')}

    # Loop through the DataFrame to find where a new week starts
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    if isinstance(day, int):
        day = weekdays[day]
    ship_week_start_indices = {}
    for ship in grouped_dfs:
        # Create a list to hold the indices where a new week starts
        week_start_indices = [0]
        grouped_df = grouped_dfs[ship]
        for i in range(len(grouped_df) - 1):
            ind = weekdays.index(grouped_df.iloc[i]['Start_Weekday'])
            ind_next = weekdays.index(grouped_df.iloc[i + 1]['Start_Weekday'])
            if (ind_next >= weekdays.index(day)
                    and ((ind_next > ind and ind < weekdays.index(day)) or (ind_next < ind and ind > weekdays.index(day)))):
                week_start_indices.append(i + 1)

        week_start_indices.append(len(grouped_df))
        ship_week_start_indices[ship] = week_start_indices

    # Create a list to hold the split DataFrames
    split_dfs = []

    # Split the DataFrame using the identified start indices
    for ship in grouped_dfs:
        grouped_df = grouped_dfs[ship]
        for start, end in zip(ship_week_start_indices[ship][:-1], ship_week_start_indices[ship][1:]):
            split_dfs.append(grouped_df.iloc[start:end])

    for split_df in split_dfs:
        split_df['Snelheid'] = split_df['Snelheid'].str.replace('km/u', '').astype(float).round(1)
        split_df['Snelheid_week_gem'] = split_df['Snelheid'].mean()
        split_df['Vaaruren_week'] = sum(split_df['Vaaruren']) / 60
        split_df['Wachttijd_week'] = sum(split_df['Wachttijd']) / 60
        split_df['Laad/Lostijd_week'] = sum(split_df['Laad/Lostijd']) / 60
        split_df['Rusttijd_week'] = sum(split_df['Rusttijd']) / 60
        split_df['Tijd onder contract'] = (sum(split_df['Vaaruren']) + sum(split_df['Wachttijd'])
                                           + sum(split_df['Laad/Lostijd'])) / 60

    df = pd.concat(split_dfs, ignore_index=True)

    return df


def assign_default_value_as_contract_hours(df, value=112):
    ships = df['Schip'].unique().tolist()
    ship_config = pd.DataFrame({'Schip': ships})
    ship_config['Contracturen'] = value
    return ship_config


def get_required_rows(ship_config, df, filter_boolean):
    start_end = {}
    for ship in ship_config:
        filtered_df_ship = df[df['Schip'] == ship]
        if filter_boolean:
            contract_hours = ship_config[ship]
            filtered_df_ship = filtered_df_ship[filtered_df_ship['Tijd onder contract'] < contract_hours]
        grouped = filtered_df_ship.groupby('Tijd onder contract')['Tijd onder contract']

        # Get first and last occurrence indices
        first_indices = grouped.head(1).index
        last_indices = grouped.tail(1).index

        # Concatenate the first and last rows
        first_last_rows = pd.concat([filtered_df_ship.loc[first_indices],
                                     filtered_df_ship.loc[last_indices]]).sort_index()
        first_last_rows = first_last_rows.reset_index()

        if filter_boolean:
            for i in range(0, len(first_last_rows) - 1, 2):
                if first_last_rows.loc[i, 'Start'] in start_end:
                    start_end[first_last_rows.loc[i, 'Start']].append({'End': first_last_rows.loc[i + 1, 'Einde'], 'Ship': ship})
                else:
                    start_end[first_last_rows.loc[i, 'Start']] = [{'End': first_last_rows.loc[i + 1, 'Einde'], 'Ship': ship}]
        else:
            for i in range(0, len(first_last_rows) - 1, 2):
                start_end[first_last_rows.loc[i, 'Start']] = [first_last_rows.loc[i + 1, 'Einde'], ship]

    sorted_options = sorted(list(start_end.keys()))
    options_as_dates = {}
    for item in sorted_options:
        options_as_dates[item.date()] = item

    return start_end, options_as_dates


# Assuming 'df' is your DataFrame with 'Start' and 'Einde' columns in datetime format
def split_rows_on_day_change(df):
    df = df.drop(columns=['index'])  # Drop the 'index' column

    # Prepare a list to hold new rows
    new_rows = []

    # Loop through the DataFrame and check for the condition
    for index, row in df.iterrows():
        start_date = row['Start'].date()
        end_date = row['Einde'].date()
        # Loop through each day from start to end
        if (end_date - start_date).days >= 1:
            for single_date in pd.date_range(start=start_date, end=end_date):
                if single_date.date() == start_date:
                    # For the start date, calculate until the end of that day
                    start = row['Start']
                    end = pd.Timestamp(year=start_date.year, month=start_date.month, day=start_date.day, hour=23,
                                       minute=59, second=59)
                elif single_date.date() == end_date:
                    # For the end date, calculate from the start of that day
                    start = pd.Timestamp(year=end_date.year, month=end_date.month, day=end_date.day)
                    end = row['Einde']
                else:
                    # For the days in between, start at 00:00 and end at 23:59:59
                    start = pd.Timestamp(year=single_date.year, month=single_date.month, day=single_date.day)
                    end = pd.Timestamp(year=single_date.year, month=single_date.month, day=single_date.day, hour=23,
                                       minute=59, second=59)

                # Calculate the time difference
                time_difference = end - start
                difference_in_minutes = math.ceil(time_difference.total_seconds() / 60)

                # Determine the appropriate time category
                vaaruren = row['Vaaruren']
                wachttijd = row['Wachttijd']
                rusttijd = row['Rusttijd']
                laad_lostijd = row['Laad/Lostijd']
                if vaaruren > 0:
                    vaaruren = difference_in_minutes
                elif wachttijd > 0:
                    wachttijd = difference_in_minutes
                elif rusttijd > 0:
                    rusttijd = difference_in_minutes
                else:
                    laad_lostijd = difference_in_minutes

                # Append the new row for this day
                new_rows.append({
                    'Start': start,
                    'Einde': end,
                    'Van': row['Van'],
                    'Tot': row['Tot'],
                    'Vaaruren': vaaruren,
                    'Wachttijd': wachttijd,
                    'Rusttijd': rusttijd,
                    'Laad/Lostijd': laad_lostijd,
                    'Snelheid': row['Snelheid'],
                    'Schip': row['Schip'],
                    'Start_Date': start.date(),
                    'Einde_Date': start.date(),
                    'Start_Weekday': start.strftime('%A'),
                    'Einde_Weekday': start.strftime('%A')
                })
        else:
            # If not splitting, keep the original row
            new_rows.append(row.to_dict())  # Convert row to dictionary to keep all columns

    # Create a new DataFrame from the new rows
    new_df = pd.DataFrame(new_rows)

    return new_df


# Generic function to get week number with a custom start of the week
def week_number_custom_start(dt, start_weekday):
    """
    Get the week number with a custom start day of the week.

    Parameters:
    dt (datetime): The input date.
    start_weekday (int): The start of the week (0 = Monday, 6 = Sunday).

    Returns:
    str: The week number as a string.
    """

    dt = pd.to_datetime(dt)
    start_weekday = weekday_string_to_int(start_weekday)

    # Adjust the date based on the custom start weekday
    shift_days = (dt.weekday() - start_weekday + 7) % 7
    adjusted_date = dt - pd.Timedelta(days=shift_days)

    # Return the week number with Sunday as the start (after adjustment)
    return adjusted_date.strftime('%U')

def weekday_string_to_int(weekday_str):
    # Mapping of weekday strings to integers
    weekday_map = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6
    }
    return weekday_map.get(weekday_str)
