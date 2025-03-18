import pandas as pd
from pymongo import MongoClient
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from bson import DBRef

# ------------------- Login Page -------------------
def login():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == "admin" and password == "password123":
            st.session_state.logged_in = True
            st.rerun()

        else:
            st.error("Invalid credentials. Please try again.")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

# ------------------- MongoDB Connection -------------------
uri = "mongodb+srv://readOnlyUser:DoffairReadDev@development-cluster.9w53x.mongodb.net/doffair_dev?retryWrites=true&w=majority"
client = MongoClient(uri)
db = client["doffair_dev"]

# Helper function to handle DBRef fields
def remove_dbref(doc):
    return {k: v if not isinstance(v, DBRef) else str(v) for k, v in doc.items()}

# ------------------- Fetch Data -------------------
users_df = pd.DataFrame([remove_dbref(doc) for doc in db["users"].find({}, {"_id": 1})])
pets_df = pd.DataFrame([remove_dbref(doc) for doc in db["pets"].find({}, {"_id": 1, "userId": 1, "breed": 1, "createdAt": 1, "likeList": 1, "unlikedList": 1, "superLike": 1})])
user_info_df = pd.DataFrame([remove_dbref(doc) for doc in db["userInfo"].find({}, {"_id": 1, "userId": 1, "location": 1})])

# Extract coordinates for map
if "location" in user_info_df.columns and not user_info_df.empty:
    def extract_coordinates(loc):
        if isinstance(loc, dict) and "coordinates" in loc:
            try:
                lon, lat = loc["coordinates"]
                return pd.Series([lon, lat])
            except:
                return pd.Series([None, None])
        return pd.Series([None, None])

    user_info_df[["longitude", "latitude"]] = user_info_df["location"].apply(extract_coordinates)
    map_df = user_info_df.dropna(subset=["longitude", "latitude"])[["longitude", "latitude"]]
else:
    map_df = pd.DataFrame(columns=["longitude", "latitude"])

# ------------------- Basic Metrics -------------------
total_users = len(users_df)
total_pets = len(pets_df)

# Breed distribution
breed_distribution = pets_df["breed"].value_counts().reset_index() if "breed" in pets_df.columns and not pets_df.empty else pd.DataFrame(columns=["breed", "count"])
breed_distribution.columns = ["breed", "count"]

# ------------------- Streamlit Layout -------------------
st.title("🐾 Doffair Analytics Dashboard")

# Show total users and pets in bar chart with labels
counts_df = pd.DataFrame({
    "Category": ["Total Users", "Total Pets"],
    "Count": [total_users, total_pets]
})
st.subheader("Total Number of Pets and User Count")
fig_count = go.Figure(data=[go.Bar(
    x=counts_df["Category"],
    y=counts_df["Count"],
    text=counts_df["Count"],
    textposition='auto',
    marker_color=['#636EFA', '#EF553B']
)])
fig_count.update_layout(title="Total Number of Pets and User Count")
st.plotly_chart(fig_count)

# ------------------- Pet Breed Pie Chart -------------------
if not breed_distribution.empty:
    st.subheader("Pet Distribution by Breed")
    fig_breed = px.pie(breed_distribution, names="breed", values="count", title="Pet Distribution by Breed")
    st.plotly_chart(fig_breed)
else:
    st.warning("No breed data available.")

# ------------------- Active Users Over Time (Pet Registrations) -------------------
if "createdAt" in pets_df.columns and not pets_df.empty:
    pets_df["createdAt"] = pd.to_datetime(pets_df["createdAt"])
    active_users_over_time = pets_df.resample("M", on="createdAt").count().reset_index()
    active_users_over_time = active_users_over_time.rename(columns={"_id": "new_pets_registered"})

    st.subheader("New Pets Registered Over Time")
    fig_time = px.line(active_users_over_time, x="createdAt", y="new_pets_registered", title="New Pets Registered Over Time")
    st.plotly_chart(fig_time)
else:
    st.warning("No registration date data available.")

# ------------------- Map Visualization -------------------
if not map_df.empty:
    st.subheader("User Locations on Map")
    st.map(map_df)
else:
    st.warning("No valid location data available.")

# ------------------- Swipe Insights with Date Filters -------------------
st.header("📅 Swipe Insights (Date-wise filter)")

start_date = st.date_input("Start Date", value=datetime(2024, 1, 1))
end_date = st.date_input("End Date", value=datetime.today())

start_datetime = pd.to_datetime(start_date)
end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1)

# Filter pets_df by createdAt
filtered_swipes = pets_df[(pets_df["createdAt"] >= start_datetime) & (pets_df["createdAt"] < end_datetime)]

# Swipe counts
total_swipe_right = filtered_swipes["likeList"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
total_swipe_left = filtered_swipes["unlikedList"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
total_super_likes = filtered_swipes["superLike"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()

swipe_data = pd.DataFrame({
    "Action": ["Swipe Right", "Swipe Left", "Super Likes"],
    "Count": [total_swipe_right, total_swipe_left, total_super_likes]
})

st.subheader("Swipe Counts (filtered by date)")
fig_swipes = go.Figure(data=[go.Bar(
    x=swipe_data["Action"],
    y=swipe_data["Count"],
    text=swipe_data["Count"],
    textposition='auto',
    marker_color=['#00CC96', '#EF553B', '#AB63FA']
)])
fig_swipes.update_layout(title=f"Swipes from {start_date} to {end_date}")
st.plotly_chart(fig_swipes)
