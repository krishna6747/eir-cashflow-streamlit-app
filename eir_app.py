import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import brentq

st.set_page_config(page_title="EIR Cashflow Treasury", layout="wide")

st.title("📊 EIR Cashflow Treasury Calculator")

# -------------------------------
# Inputs
# -------------------------------
uploaded_file = st.file_uploader("Upload Cashflow Excel File", type=["xlsx"])
new_balance = st.number_input("Enter New Balance", value=0.0, step=1000.0)
loan_availment_date = st.date_input("Enter Loan Availment Date")

if uploaded_file and new_balance > 0:
    # Load Data
    df = pd.read_excel(uploaded_file)

    # Function to clean numeric columns
    def clean_numeric(col):
        return (
            col.astype(str)
               .str.replace(",", "", regex=False)
               .str.replace("-", "0", regex=False)
               .astype(float)
               .round(2)
        )

    # Apply cleaning
    for col in df.columns:
        if col != "Date":
            df[col] = clean_numeric(df[col])

    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
    df["Installment Amount"] = df["Installment Amount"].fillna(0).astype(float)

    # -------------------------------
    # EIR Calculation
    # -------------------------------
    def simulate_cashflow(eir):
        opening_balance = new_balance
        previous_date = pd.to_datetime(loan_availment_date)
        closing_balance = opening_balance

        for _, row in df.iterrows():
            date = row["Date"]
            installment = row["Installment Amount"]
            days = (date - previous_date).days
            interest = opening_balance * eir / 365 * days
            closing_balance = opening_balance + interest - installment
            opening_balance = closing_balance
            previous_date = date
        return closing_balance

    eir_solution = brentq(simulate_cashflow, 0.0001, 1.0)
    st.success(f"✅ Effective Interest Rate (EIR): {eir_solution*100:.6f}%")

    # -------------------------------
    # Cashflow Schedule
    # -------------------------------
    rows = []
    opening_balance = new_balance
    previous_date = pd.to_datetime(loan_availment_date)
    cumulative_additional_interest = 0

    for _, row in df.iterrows():
        date = row["Date"]
        installment = row["Installment Amount"]
        original_interest = row["Interest Due"]

        days = (date - previous_date).days
        interest = opening_balance * eir_solution / 365 * days
        closing_balance = opening_balance + interest - installment

        additional_interest = interest - original_interest
        cumulative_additional_interest += additional_interest

        rows.append({
            "Date": date,
            "Opening Balance": round(opening_balance),
            "Interest (EIR Calc)": round(interest, 2),
            "Original Interest": round(original_interest, 2),
            "Additional Interest due to EIR": round(additional_interest, 2),
            "Cumulative Additional Interest": round(cumulative_additional_interest, 2),
            "Installment": installment,
            "Closing Balance": round(closing_balance),
            "No. of Days": days,
        })

        opening_balance = closing_balance
        previous_date = date

    cashflow_df = pd.DataFrame(rows)
    st.subheader("📑 EIR Cashflow Schedule")
    st.dataframe(cashflow_df.head(10))

    # Download button
    csv_cashflow = cashflow_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Cashflow Schedule CSV", data=csv_cashflow, file_name="cashflow_schedule.csv")

    # -------------------------------
    # Reporting Month End Calculation
    # -------------------------------
    df_rep = cashflow_df.copy()
    df_rep['Date'] = pd.to_datetime(df_rep['Date'], dayfirst=True)
    real_month_ends = set(df_rep['Date'][df_rep['Date'].dt.is_month_end])

    reporting_rows = []
    first = df_rep.iloc[0]
    opening_balance = float(first["Opening Balance"])
    cumulative_add = float(first["Additional Interest due to EIR"])

    reporting_rows.append({
        "Date": first["Date"],
        "Opening Balance": int(round(opening_balance)),
        "Interest (EIR Calc)": int(round(first["Interest (EIR Calc)"])),
        "Original Interest": int(round(first["Original Interest"])),
        "Additional Interest due to EIR": int(round(first["Additional Interest due to EIR"])),
        "Cumulative Additional Interest": int(round(cumulative_add)),
        "Installment": int(first["Installment"]),
        "Closing Balance": int(round(opening_balance + first["Interest (EIR Calc)"] - first["Installment"])),
        "No. of Days": int(first["No. of Days"])
    })

    for i in range(1, len(df_rep)):
        prev = df_rep.iloc[i - 1]
        curr = df_rep.iloc[i]
        prev_date = pd.to_datetime(prev["Date"])
        curr_date = pd.to_datetime(curr["Date"])
        opening_balance = reporting_rows[-1]["Closing Balance"]

        total_days = (curr_date - prev_date).days
        if total_days <= 0:
            total_days = 1

        eir_full = float(curr["Interest (EIR Calc)"])
        orig_full = float(curr["Original Interest"])
        month_ends = pd.date_range(prev_date, curr_date, freq="M")
        last_anchor = prev_date

        for m in month_ends:
            if m < curr_date and m not in real_month_ends:
                days_till_me = (m - prev_date).days
                prorated_eir = eir_full / total_days * days_till_me
                prorated_orig = orig_full / total_days * days_till_me
                addl = prorated_eir - prorated_orig
                cumulative_add += addl
                closing_me = opening_balance + prorated_eir

                reporting_rows.append({
                    "Date": m,
                    "Opening Balance": int(round(opening_balance)),
                    "Interest (EIR Calc)": int(round(prorated_eir)),
                    "Original Interest": int(round(prorated_orig)),
                    "Additional Interest due to EIR": int(round(addl)),
                    "Cumulative Additional Interest": int(round(cumulative_add)),
                    "Installment": "",
                    "Closing Balance": int(round(closing_me)),
                    "No. of Days": int(days_till_me)
                })
                opening_balance = closing_me
                last_anchor = m

        rem_days = (curr_date - last_anchor).days
        if rem_days <= 0:
            rem_days = total_days
        rem_eir = eir_full / total_days * rem_days
        rem_orig = orig_full / total_days * rem_days
        addl = rem_eir - rem_orig
        cumulative_add += addl
        closing_inst = opening_balance + rem_eir - float(curr["Installment"])

        reporting_rows.append({
            "Date": curr_date,
            "Opening Balance": int(round(opening_balance)),
            "Interest (EIR Calc)": int(round(rem_eir)),
            "Original Interest": int(round(rem_orig)),
            "Additional Interest due to EIR": int(round(addl)),
            "Cumulative Additional Interest": int(round(cumulative_add)),
            "Installment": int(curr["Installment"]),
            "Closing Balance": int(round(closing_inst)),
            "No. of Days": int(total_days)
        })

    reporting_df = pd.DataFrame(reporting_rows).sort_values("Date").reset_index(drop=True)
    reporting_df["Date"] = pd.to_datetime(reporting_df["Date"]).dt.strftime("%d-%m-%Y")

    st.subheader("📊 Reporting Dates Cashflow")
    st.dataframe(reporting_df.tail(10))

    # Download button
    csv_reporting = reporting_df.to_csv(index=False).encode("utf-8")

    st.download_button("⬇️ Download Reporting Dates CSV", data=csv_reporting, file_name="reporting_cashflow.csv")
