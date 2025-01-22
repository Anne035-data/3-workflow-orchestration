import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import os
import time
from sqlalchemy.exc import OperationalError


# Configuration de la page
st.set_page_config(
    page_title="Fraud Detection Dashboard",
    page_icon="🕵️",
    layout="wide"
)

# Connexion à Neon avec retry
@st.cache_resource
def init_connection():
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(os.environ["NEON_DATABASE_URL"])
            # Test the connection
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return engine
        except Exception as e:
            if attempt < max_retries - 1:
                st.warning(f"Tentative de reconnexion à la base de données ({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                st.error(f"Erreur de connexion à la base de données: {str(e)}")
                raise

# Récupération des données avec gestion d'erreurs
@st.cache_data(ttl=600)
def get_data(query, error_message="Erreur lors de la récupération des données"):
    try:
        conn = init_connection()
        return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"{error_message}: {str(e)}")
        return pd.DataFrame()

# Fonctions de récupération des données
def get_recent_transactions():
    return get_data("""
        SELECT * FROM recent_transactions 
        WHERE trans_date_trans_time >= NOW() - INTERVAL '24 hours'
        ORDER BY trans_date_trans_time DESC
    """, "Erreur lors de la récupération des transactions récentes")

def get_yesterday_metrics():
    return get_data("""
        SELECT * FROM yesterday_transactions
    """, "Erreur lors de la récupération des données d'hier")

def get_daily_stats():
    return get_data("""
        SELECT * FROM daily_stats 
        ORDER BY date DESC 
        LIMIT 7
    """, "Erreur lors de la récupération des statistiques quotidiennes")

def get_merchant_stats():
    return get_data("""
        SELECT merchant, COUNT(*) AS total_transactions,
               SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS fraud_transactions,
               ROUND((SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::decimal / COUNT(*)) * 100, 2) AS fraud_rate
        FROM recent_transactions
        GROUP BY merchant
        ORDER BY fraud_rate DESC, total_transactions DESC
        LIMIT 10
    """, "Erreur lors de la récupération des statistiques des marchands")

# UI Principal
def main():
    st.title("🕵️ Fraud Detection Dashboard")
    st.subheader("Surveillance en temps réel des transactions")

    # Ajout d'un bouton de rafraîchissement
    if st.button("🔄 Rafraîchir les données"):
        st.cache_data.clear()
        st.experimental_rerun()

    try:
        # Métriques de la veille
        yesterday_data = get_yesterday_metrics()
        if not yesterday_data.empty:
            st.markdown("### 📅 Bilan de la veille")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Transactions", yesterday_data['total_transactions'].iloc[0])
            with col2:
                st.metric("Fraudes détectées", yesterday_data['fraud_count'].iloc[0])
            with col3:
                st.metric("Taux de fraude", f"{yesterday_data['fraud_rate'].iloc[0]}%")
            with col4:
                st.metric("Montant total", f"${yesterday_data['total_amount'].iloc[0]:,.2f}")

        # Statistiques des dernières 24h
        stats = get_daily_stats()
        if not stats.empty:
            st.markdown("### ⚡ Dernières 24 heures")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Transactions (24h)", stats.iloc[0]["total_transactions"])
            with col2:
                st.metric("Fraudes détectées", stats.iloc[0]["fraud_count"])
            with col3:
                st.metric("Taux de fraude", f"{stats.iloc[0]['fraud_rate']:.2f}%")
            with col4:
                st.metric("Montant total", f"${stats.iloc[0]['total_amount']:,.2f}")
            with col5:
                avg_fraud_prob = stats["fraud_rate"].mean()
                st.metric("Probabilité moyenne de fraude", f"{avg_fraud_prob:.2f}%")

            # Graphiques
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Evolution du taux de fraude")
                fig = px.line(stats, x="date", y="fraud_rate", 
                             title="Taux de fraude sur 7 jours")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Montant des transactions")
                fig = px.bar(stats, x="date", y="total_amount",
                            title="Montant total des transactions par jour")
                st.plotly_chart(fig, use_container_width=True)

        # Statistiques par marchand
        merchants = get_merchant_stats()
        if not merchants.empty:
            st.subheader("Top 10 des marchands par taux de fraude")
            st.dataframe(merchants)

        # Dernières transactions
        transactions = get_recent_transactions()
        if not transactions.empty:
            st.subheader("Dernières transactions")
            
            if transactions["is_fraud"].sum() > 0:
                st.error("⚠️ Fraude détectée dans les dernières transactions !")
            
            amount_filter = st.slider(
                "Montant minimum de la transaction", 
                min_value=0, 
                max_value=int(transactions["amt"].max()), 
                value=0
            )
            
            fraud_filter = st.checkbox("Afficher seulement les transactions frauduleuses")
            filtered_transactions = transactions[transactions["amt"] >= amount_filter]
            
            if fraud_filter:
                filtered_transactions = filtered_transactions[filtered_transactions["is_fraud"]]
            
            st.dataframe(
                filtered_transactions[["trans_date_trans_time", "merchant", "amt", "city", 
                                   "is_fraud", "fraud_probability"]],
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Une erreur est survenue lors du chargement du dashboard: {str(e)}")
        st.warning("Veuillez vérifier la connexion à la base de données et réessayer.")

if __name__ == "__main__":
    main()