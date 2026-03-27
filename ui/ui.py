import streamlit as st
from api.nutrition_api import search_food


def launch_ui():
    st.title("Calorie Tracker")