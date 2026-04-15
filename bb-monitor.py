import streamlit as st

pages = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon=":material/home:"),
    st.Page(
        "pages/2_Single_Stations.py",
        title="Single Stations",
        icon=":material/monitoring:",
    ),
]

pg = st.navigation(pages, position="top")
pg.run()
