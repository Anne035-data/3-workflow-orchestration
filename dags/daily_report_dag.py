from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from utils.common import logger, get_db_engine, send_email

def send_daily_report(**context):
    try:
        engine = get_db_engine()
        yesterday = (datetime.now() - timedelta(days=1)).date()
        
        query = "SELECT * FROM yesterday_transactions"
        result = engine.execute(query).fetchone()
        
        if not result:
            logger.warning(f"Pas de données pour le {yesterday}")
            return
            
        body = f"""Rapport des transactions du {yesterday}

📊 Résumé des transactions :
---------------------------
Nombre total de transactions : {result.total_transactions:,}
Nombre de fraudes détectées : {result.fraud_count:,}
Taux de fraude : {result.fraud_rate}%

💰 Données financières :
---------------------
Montant total : ${result.total_amount:,.2f}
Montant moyen : ${result.avg_amount:,.2f}
Montant max : ${result.max_amount:,.2f}
Montant des transactions normales : ${result.normal_amount:,.2f}
Montant total des fraudes : ${result.fraud_amount:,.2f}

📊 Analyse détaillée disponible sur :
-----------------------------------
- Dashboard Streamlit : http://localhost:8501
- Suivi des prédictions : http://localhost:5000 (MLflow)
"""
        send_email(
            subject=f"📈 Rapport quotidien des transactions - {yesterday}",
            body=body
        )
        logger.info(f"Rapport quotidien envoyé pour le {yesterday}")
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport : {str(e)}")
        raise

default_args = {
    'owner': 'fraud_team',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'daily_transactions_report',
    default_args=default_args,
    description='Envoi du rapport quotidien des transactions',
    schedule_interval='0 6 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False
) as dag:

    report_task = PythonOperator(
        task_id='send_daily_report',
        python_callable=send_daily_report,
        provide_context=True
    )