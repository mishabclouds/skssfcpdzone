import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageOps
import qrcode
import io
import cv2
import numpy as np
import os
from datetime import datetime

st.set_page_config(page_title="SKSSF VIVISE Registration", page_icon="⏳", layout="centered")

# --- UI TWEAKS FOR MOBILE ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            /* Add padding to the top for mobile phone notches/safe areas */
            .block-container {padding-top: 1rem; padding-bottom: 2rem;} 
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 1. INITIALIZATION ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("participants.csv")
        df['Mobile'] = df['Mobile'].astype(str).str.strip()
        df['Membership'] = df['Membership'].astype(str).str.strip()
        return df
    except FileNotFoundError:
        st.error("Database file 'participants.csv' not found. Please run your extraction script first.")
        return pd.DataFrame()

db = load_data()

# Ensure required files and folders exist
if not os.path.exists("attendance.csv"):
    pd.DataFrame(columns=["Membership", "Name", "CheckInTime"]).to_csv("attendance.csv", index=False)

if not os.path.exists("registrations_log.csv"):
    pd.DataFrame(columns=["Timestamp", "Membership", "Name", "Attending", "WhatsApp"]).to_csv("registrations_log.csv", index=False)

if not os.path.exists("passes"):
    os.makedirs("passes")

# --- APP NAVIGATION ---
tab1, tab2 = st.tabs(["🖱️ Participant Registration", "🔒 Admin Control Panel"])

# ==========================================
# TAB 1: REGISTRATION & POSTER GENERATION
# ==========================================
with tab1:
    # --- NEW: Add the Banner Image ---
    try:
        st.image("banner.jpg", width='stretch')
    except FileNotFoundError:
        pass # If you don't have a banner yet, the app won't crash
        
    st.title("Registration Portal")
    # --- NEW: DEADLINE LOGIC (Adjusted for IST) ---
    from datetime import timedelta
    
    # Calculate current IST time (UTC + 5 hours 30 minutes)
    current_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    
    # SET YOUR DEADLINE HERE: datetime(Year, Month, Day, Hour, Minute)
    # Note: Use 24-hour format for the hour. 
    # Example below is set for August 1, 2026, at 10:00 PM (22:00)
    deadline = datetime(2026, 8, 1, 22, 0)
    
    if current_ist > deadline:
        # What users see after the deadline passes
        st.error("🚨 Registration is now closed.")
        st.info("The deadline to register for this program has passed. If you are already registered but lost your pass, please contact the administrator at the venue.")
    else:
        # What users see before the deadline
        st.subheader("Validate your details & generate your official entry pass")
        
        time_left = deadline - current_ist
        days, seconds = time_left.days, time_left.seconds
        hours = seconds // 3600
        st.caption(f"⏳ Time remaining to register: {days} days, {hours} hours")
        
        search_query = st.text_input("Enter your Registered Mobile Number or Membership ID:", "").strip()
        
        if search_query and not db.empty:
            matched = db[(db['Mobile'] == search_query) | (db['Membership'] == search_query)]
            
            if matched.empty:
                st.error("No record found with this Mobile Number or Membership ID. Please check and try again.")
            else:
                user_data = matched.iloc[0].to_dict()
                st.success(f"Record Verified for **{user_data.get('Name')}**!")
                
                membership_id = str(user_data.get('Membership'))
                safe_membership = membership_id.replace('/', '_')
                
                reg_df = pd.read_csv("registrations_log.csv")
                is_registered = membership_id in reg_df['Membership'].astype(str).values
                
                if is_registered:
                    st.info("✅ You have already successfully registered for this program!")
                    
                    pass_path = f"passes/Pass_{safe_membership}.jpg"
                    
                    if os.path.exists(pass_path):
                        st.image(pass_path, caption="Your Event Entry Pass", width='stretch')
                        
                        with open(pass_path, "rb") as file:
                            st.download_button(
                                label="📥 Download Pass Again",
                                data=file,
                                file_name=f"Pass_{safe_membership}.jpg",
                                mime="image/jpeg"
                            )
                    else:
                        st.warning("We have your registration on file, but couldn't find your pass image. Please contact the administrator.")
                
                else:
                    with st.form("registration_form"):
                        st.markdown("### 📋 Confirm Your Information")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Designation:** {user_data.get('Designation')}")
                            st.write(f"**Unit:** {user_data.get('Unit')}")
                            st.write(f"**Cluster:** {user_data.get('Cluster')}")
                            st.write(f"**Registered Mobile:** {user_data.get('Mobile')}")
                        with col2:
                            st.write(f"**Zone:** {user_data.get('Zone')}")
                            st.write(f"**District:** {user_data.get('District')}")
                            st.write(f"**Membership:** {user_data.get('Membership')}")

                        st.markdown("---")

                        attendance = st.radio("Will you be attending the program?", ["Yes", "No"], index=0)
                        
                        wa_same = st.radio(
                            f"Is your WhatsApp number the same as your registered mobile number ({user_data.get('Mobile')})?", 
                            ["Yes", "No"]
                        )
                        
                        whatsapp_no = user_data.get('Mobile')
                        if wa_same == "No":
                            whatsapp_no = st.text_input("Enter your WhatsApp Number:", value="").strip()
                        
                        uploaded_photo = st.file_uploader("Upload your profile photo (JPG/PNG):", type=["jpg", "jpeg", "png"])
                        
                        submit_btn = st.form_submit_button("Complete Registration & Generate Pass")

                    if submit_btn:
                        if attendance == "No":
                            reg_data = pd.DataFrame([{
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Membership": membership_id,
                                "Name": user_data.get('Name'),
                                "Attending": attendance,
                                "WhatsApp": whatsapp_no
                            }])
                            reg_data.to_csv("registrations_log.csv", mode='a', header=False, index=False)
                            st.info("Thank you for updating your status. We hope to see you at future events!")
                            
                        elif not uploaded_photo:
                            st.error("Please upload a profile photo to complete your pass generation.")
                            
                        else:
                            reg_id = f"REG-{membership_id}"
                            
                            qr = qrcode.QRCode(version=1, box_size=6, border=2)
                            qr.add_data(reg_id)
                            qr.make(fit=True)
                            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                            
                           # --- GENERATE POSTER USING VIVISE TEMPLATE ---
                            template_path = "template.jpg"
                            
                            if os.path.exists(template_path):
                                poster = Image.open(template_path).convert("RGB")
                                poster = poster.resize((800, 1067)) 
                                draw = ImageDraw.Draw(poster)
                                
                                # --- 1. Place the QR Code (<QR>) ---
                                # FIX: Set border=0 to remove the thick white box entirely
                                qr = qrcode.QRCode(version=1, box_size=6, border=0) 
                                qr.add_data(reg_id)
                                qr.make(fit=True)
                                qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                                
                                qr_size = 145 # Sized exactly for the top-left box
                                qr_img_resized = qr_img.resize((qr_size, qr_size))
                                poster.paste(qr_img_resized, (28, 25)) # Calibrated X, Y coordinates
                                
                                # --- 2. Place the User Photo (<PHOTO>) with SMART CROP ---
                                photo_width, photo_height = 205, 275 # Exact dimensions of the gray box
                                raw_photo = Image.open(uploaded_photo).convert("RGB")
                                
                                # ImageOps.fit automatically crops to the box size without squishing.
                                # centering=(0.5, 0.15) anchors the crop near the top so faces aren't cut off!
                                user_photo = ImageOps.fit(raw_photo, (photo_width, photo_height), centering=(0.5, 0.15))
                                
                                # Calibrated coordinates to cover the gray box entirely
                                poster.paste(user_photo, (103, 622)) 
                                
                                # --- 3. Place the Text (<NAME> and <UNIT>) ---
                                try:
                                    from PIL import ImageFont
                                    font_large = ImageFont.truetype("Montserrat-Medium.ttf", 36)
                                    font_medium = ImageFont.truetype("Montserrat-Medium.ttf", 28)
                                except Exception as e:
                                    font_large = None
                                    font_medium = None
                                
                                draw.text((350, 790), str(user_data.get('Name')), fill=(255, 255, 255), font=font_large)
                                draw.text((350, 840), str(user_data.get('Unit')), fill=(200, 200, 200), font=font_medium)
                                
                            else:
                                # Fallback if template.jpg is missing
                                card_width, card_height = 800, 1000
                                poster = Image.new("RGB", (card_width, card_height), color=(245, 247, 250))
                                draw = ImageDraw.Draw(poster)
                                draw.rectangle([(0, 0), (card_width, 140)], fill=(0, 138, 69))
                                draw.text((40, 45), "OFFICIAL ENTRY PASS", fill=(255, 255, 255))
                                photo_img = Image.open(uploaded_photo).convert("RGB").resize((220, 220))
                                poster.paste(photo_img, (50, 180))
                                draw.text((300, 180), f"Name: {user_data.get('Name')}", fill=(0, 0, 0))
                                draw.text((300, 230), f"ID: {reg_id}", fill=(200, 30, 30))
                                draw.text((300, 280), f"Unit: {user_data.get('Unit')}", fill=(50, 50, 50))
                                qr_img_resized = qr_img.resize((200, 200))
                                poster.paste(qr_img_resized, (550, 740))

                            pass_path = f"passes/Pass_{safe_membership}.jpg"
                            poster.save(pass_path, format="JPEG")

                            reg_data = pd.DataFrame([{
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Membership": membership_id,
                                "Name": user_data.get('Name'),
                                "Attending": attendance,
                                "WhatsApp": whatsapp_no
                            }])
                            reg_data.to_csv("registrations_log.csv", mode='a', header=False, index=False)

                            st.success("🎉 Registration Completed Successfully!")
                            st.balloons()
                            st.image(poster, caption="Your Event Entry Pass", width='stretch')
                            
                            with open(pass_path, "rb") as file:
                                st.download_button(
                                    label="📥 Download Pass to Share on WhatsApp",
                                    data=file,
                                    file_name=f"Pass_{safe_membership}.jpg",
                                    mime="image/jpeg"
                                )

# ==========================================
# TAB 2: VENUE QR SCANNER & ADMIN DASHBOARD
# ==========================================
with tab2:
    st.title("🔒 Admin Control Panel")
    
    admin_password = st.text_input("Enter Admin Password:", type="password")
    
    if admin_password == "skssf123":
        st.success("Admin Access Granted")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 Registration Monitor", "📈 Follow-up Tracker", "📷 Venue Scanner"])
        
        # --- SUB-TAB 1: REGISTRATION MONITOR ---
        with admin_tab1:
            st.subheader("Live Registration Updates")
            try:
                reg_df = pd.read_csv("registrations_log.csv")
                st.dataframe(reg_df, width='stretch')
                
                reg_csv = reg_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Registration Data", data=reg_csv, file_name="registrations_log.csv", mime="text/csv")
            except FileNotFoundError:
                st.write("No registrations yet.")
        
        # --- SUB-TAB 2: FOLLOW-UP TRACKER ---
        with admin_tab3:
            st.subheader("Unit & Cluster Follow-Up Tracker")
            st.write("Track registration progress across different regions.")
            
            if not db.empty:
                try:
                    reg_df = pd.read_csv("registrations_log.csv")
                    reg_members = reg_df['Membership'].astype(str).tolist()
                except FileNotFoundError:
                    reg_members = []
                
                # Create a tracking dataframe
                tracker_df = db.copy()
                tracker_df['Registered'] = tracker_df['Membership'].astype(str).isin(reg_members)
                
                view_option = st.radio("View Analytics By:", ["Cluster", "Unit"], horizontal=True)
                
                # Calculate aggregate statistics
                stats = tracker_df.groupby(view_option).agg(
                    Total_Expected=('Membership', 'count'),
                    Total_Registered=('Registered', 'sum')
                ).reset_index()
                
                stats['Pending'] = stats['Total_Expected'] - stats['Total_Registered']
                stats['Completion (%)'] = ((stats['Total_Registered'] / stats['Total_Expected']) * 100).round(1).astype(str) + '%'
                
                # Sort by Completion percentage (lowest first, to prioritize follow-up)
                stats = stats.sort_values(by=['Total_Registered', 'Total_Expected'], ascending=[True, False])
                
                st.dataframe(stats, width='stretch', hide_index=True)
                
                # Visual Metric Cards
                total_expected = len(db)
                total_registered = len(reg_members)
                total_pending = total_expected - total_registered
                overall_percent = round((total_registered / total_expected) * 100, 1) if total_expected > 0 else 0
                
                st.markdown("### Overall Progress")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Expected", total_expected)
                c2.metric("Registered", total_registered)
                c3.metric("Pending", total_pending)
                c4.metric("Completion", f"{overall_percent}%")

            else:
                st.info("Database is empty. Please ensure participants.csv is loaded.")

        # --- SUB-TAB 3: VENUE SCANNER ---
        with admin_tab2:
            st.subheader("Venue Check-In Scanner")
            st.write("Use this to scan participant passes at the door.")
            
            img_file = st.camera_input("Scan QR Code")
            
            if img_file:
                bytes_data = img_file.getvalue()
                cv_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                
                detector = cv2.QRCodeDetector()
                data, _, _ = detector.detectAndDecode(cv_img)
                
                if data:
                    scanned_id = data.replace("REG-", "")
                    
                    attendee = db[db['Membership'] == scanned_id]
                    if not attendee.empty:
                        name = attendee.iloc[0]['Name']
                        st.success(f"✅ Verified: {name} ({scanned_id})")
                        
                        log = pd.DataFrame([{"Membership": scanned_id, "Name": name, "CheckInTime": datetime.now()}])
                        log.to_csv("attendance.csv", mode='a', header=False, index=False)
                    else:
                        st.error("❌ Invalid ID or not found in database.")
                else:
                    st.warning("QR Code not detected. Please hold the pass steady.")
                    
            st.markdown("---")
            st.write("### Live Check-in Attendance")
            try:
                attendance_df = pd.read_csv("attendance.csv")
                st.dataframe(attendance_df, width='stretch')
                
                att_csv = attendance_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Attendance Report", data=att_csv, file_name="final_attendance.csv", mime="text/csv")
            except FileNotFoundError:
                st.write("No attendance data yet.")
    
    elif admin_password != "":
        st.error("Incorrect Password.")
