from pyspark.sql import SparkSession
from pyspark.sql.functions import col, length, sha2


def main() -> None:
    spark = SparkSession.builder.appName("document-quality-indexing").getOrCreate()
    bronze = spark.read.format("delta").table("docintel_bronze.raw_documents")
    silver = (
        bronze.withColumn("content_hash", sha2(col("raw_text"), 256))
        .withColumn("text_length", length(col("raw_text")))
        .filter(col("text_length") > 0)
    )
    silver.write.format("delta").mode("append").saveAsTable("docintel_silver.documents")


if __name__ == "__main__":
    main()

