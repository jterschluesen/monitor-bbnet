
# -*- coding: utf-8 -*-
# Copyright 2024-2025 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
