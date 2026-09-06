from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, length, lit, sha2


def main() -> None:
    spark = (
        SparkSession.builder.appName("agentic-document-quality-delta-job")
        .config("spark.databricks.delta.schema.autoMerge.enabled", "true")
        .getOrCreate()
    )
    bronze = spark.read.format("delta").table("docintel_bronze.raw_documents")
    silver = (
        bronze.withColumn("content_hash", sha2(col("raw_text"), 256))
        .withColumn("text_length", length(col("raw_text")))
        .withColumn("quality_job_version", lit("document-quality-v1.0.0"))
        .withColumn("processed_at", current_timestamp())
        .filter(col("text_length") > 0)
    )
    silver.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(
        "docintel_silver.documents"
    )

    gold = (
        silver.groupBy("classification")
        .count()
        .withColumnRenamed("count", "document_count")
        .withColumn("metric_version", lit("document-quality-gold-v1.0.0"))
        .withColumn("computed_at", current_timestamp())
    )
    gold.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        "docintel_gold.document_quality_metrics"
    )


if __name__ == "__main__":
    main()
