-- Uma pasta por camada do medallion. IF NOT EXISTS deixa o script rodar quantas vezes precisar.
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
