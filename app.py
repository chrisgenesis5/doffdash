import pandas as pd
from pymongo import MongoClient
import streamlit as st
import plotly.express as px
from bson import DBRef
from datetime import datetime

# ------------------- CONFIGURE HARDCODED LOGIN -------------------
USERNAME = "admin"
PASSWORD = "password123"

def login():
    st.title("Login Page")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()   # ✅ updated line
        else:
            st.error("Invalid credentials.")


if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    login()
    st.stop()

# ------------------- MONGODB CONNECTION -------------------
uri = "mongodb+srv://readOnlyUser:DoffairReadDev@development-cluster.9w53x.mongodb.net/doffair_dev?retryWrites=true&w=majority"
client = MongoClient(uri)
db = client["doffair_dev"]

# ------------------- HELPER FUNCTIONS -------------------
def remove_dbref(doc):
    return {k: v if not isinstance(v, DBRef) else str(v) for k, v in doc.items()}

# ------------------- FETCH DATA -------------------
users_df = pd.DataFrame([remove_dbref(doc) for doc in db["users"].find({}, {"_id": 1})])
pets_df = pd.DataFrame([remove_dbref(doc) for doc in db["pets"].find({}, {
    "_id": 1, "userId": 1, "breed": 1, "createdAt": 1, 
    "likeList": 1, "unlikedList": 1, "superLike": 1
})])
user_info_df = pd.DataFrame([remove_dbref(doc) for doc in db["userInfo"].find({}, {
    "_id": 1, "userId": 1, "location": 1
})])

# ------------------- PROCESS LOCATION DATA -------------------
def extract_coordinates(loc):
    if isinstance(loc, dict) and "coordinates" in loc:
        try:
            lon, lat = loc["coordinates"]
            return pd.Series([lon, lat])
        except:
            return pd.Series([None, None])
    return pd.Series([None, None])

if "location" in user_info_df.columns and not user_info_df.empty:
    user_info_df[["longitude", "latitude"]] = user_info_df["location"].apply(extract_coordinates)
    map_df = user_info_df.dropna(subset=["longitude", "latitude"])[["longitude", "latitude"]]
else:
    map_df = pd.DataFrame(columns=["longitude", "latitude"])

# ------------------- DATA AGGREGATION -------------------
total_users = len(users_df)

pets_per_user = pets_df["userId"].value_counts().reset_index() if not pets_df.empty else pd.DataFrame(columns=["userId", "pet_count"])
pets_per_user.columns = ["userId", "pet_count"]

breed_distribution = pets_df["breed"].value_counts().reset_index() if not pets_df.empty else pd.DataFrame(columns=["breed", "count"])
breed_distribution.columns = ["breed", "count"]

if "location" in user_info_df.columns and not user_info_df.empty:
    user_info_df["location_str"] = user_info_df["location"].apply(lambda loc: str(loc["coordinates"]) if isinstance(loc, dict) else None)
    location_distribution = user_info_df["location_str"].value_counts().reset_index()
    location_distribution.columns = ["location", "user_count"]
else:
    location_distribution = pd.DataFrame(columns=["location", "user_count"])

if "createdAt" in pets_df.columns and not pets_df.empty:
    pets_df["createdAt"] = pd.to_datetime(pets_df["createdAt"])
    active_users_over_time = pets_df.resample("M", on="createdAt").count().reset_index()
    active_users_over_time = active_users_over_time.rename(columns={"_id": "new_pets_registered"})
else:
    active_users_over_time = pd.DataFrame(columns=["createdAt", "new_pets_registered"])

top_users_pets = pets_per_user.nlargest(10, "pet_count") if not pets_per_user.empty else pd.DataFrame(columns=["userId", "pet_count"])
top_breeds = breed_distribution.nlargest(10, "count") if not breed_distribution.empty else pd.DataFrame(columns=["breed", "count"])

if not pets_df.empty and "location" in user_info_df.columns:
    pets_with_locations = pets_df.merge(user_info_df, on="userId", how="left")
    pet_location_distribution = pets_with_locations["location_str"].value_counts().reset_index()
    pet_location_distribution.columns = ["location", "pet_count"]
else:
    pet_location_distribution = pd.DataFrame(columns=["location", "pet_count"])

# ------------------- STREAMLIT DASHBOARD -------------------
st.title("🐾 User & Pet Analytics Dashboard")
st.header(f"Total Registered Users: {total_users}")

# --- Visualizations ---
st.subheader("Users with Number of Pets")
if not pets_per_user.empty:
    st.plotly_chart(px.bar(pets_per_user, x="userId", y="pet_count", title="Users with Number of Pets"))

st.subheader("Pet Distribution by Breed")
if not breed_distribution.empty:
    st.plotly_chart(px.pie(breed_distribution, names="breed", values="count", title="Pet Distribution by Breed"))

# st.subheader("User Count by Location")
# if not location_distribution.empty:
#     st.plotly_chart(px.bar(location_distribution, x="location", y="user_count", title="User Count by Location"))

st.subheader("Active Users Over Time (New Pets Registered)")
if not active_users_over_time.empty:
    st.plotly_chart(px.line(active_users_over_time, x="createdAt", y="new_pets_registered", title="New Pets Registered Over Time"))

st.subheader("Top 10 Users with Most Pets")
if not top_users_pets.empty:
    st.plotly_chart(px.bar(top_users_pets, x="userId", y="pet_count", title="Top 10 Users with Most Pets"))

st.subheader("Top 10 Most Popular Pet Breeds")
if not top_breeds.empty:
    st.plotly_chart(px.bar(top_breeds, x="breed", y="count", title="Top 10 Pet Breeds"))

st.subheader("Locations with Highest Pet Registrations")
if not pet_location_distribution.empty:
    st.plotly_chart(px.bar(pet_location_distribution, x="location", y="pet_count", title="Top Locations for Pet Registrations"))

st.subheader("📍 User Locations on Map")
if not map_df.empty:
    st.map(map_df)

# ------------------- NEW: DATE FILTERED SWIPE ACTION STATS -------------------
st.title("📅 Swipe Actions Insights (with Date Filter)")

if not pets_df.empty:
    start_date = st.date_input("Start Date", datetime(2024, 1, 1))
    end_date = st.date_input("End Date", datetime.today())

    filtered_pets = pets_df[(pets_df["createdAt"] >= pd.to_datetime(start_date)) & (pets_df["createdAt"] <= pd.to_datetime(end_date))]

    total_swipe_right = filtered_pets["likeList"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
    total_swipe_left = filtered_pets["unlikedList"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
    total_super_likes = filtered_pets["superLike"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()

    st.metric("Total Swipe Right", total_swipe_right)
    st.metric("Total Swipe Left", total_swipe_left)
    st.metric("Total Super Likes", total_super_likes)
else:
    st.warning("No swipe data available.")

