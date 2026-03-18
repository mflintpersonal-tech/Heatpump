/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19  Distrib 10.5.29-MariaDB, for debian-linux-gnu (aarch64)
--
-- Host: localhost    Database: heatpump
-- ------------------------------------------------------
-- Server version	10.5.29-MariaDB-0+deb11u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `aggregate_energy`
--

DROP TABLE IF EXISTS `aggregate_energy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `aggregate_energy` (
  `year` int(11) NOT NULL,
  `month` smallint(6) NOT NULL,
  `hour` smallint(6) NOT NULL,
  `total` int(11) NOT NULL,
  PRIMARY KEY (`year`,`month`,`hour`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `collections`
--

DROP TABLE IF EXISTS `collections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `collections` (
  `id` smallint(6) NOT NULL AUTO_INCREMENT,
  `description` char(30) NOT NULL,
  `parameters` varchar(50) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `commands`
--

DROP TABLE IF EXISTS `commands`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `commands` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `created` datetime NOT NULL,
  `command` char(6) NOT NULL,
  `not_before` timestamp NULL DEFAULT NULL,
  `not_after` timestamp NULL DEFAULT NULL,
  `retry` char(1) DEFAULT 'N',
  `status` int(11) DEFAULT 0,
  `executed` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `result` char(80) DEFAULT NULL,
  `values` text NOT NULL,
  PRIMARY KEY (`id`),
  KEY `i_created` (`created`),
  KEY `i_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=22819 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `control_values`
--

DROP TABLE IF EXISTS `control_values`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `control_values` (
  `parameter` char(5) NOT NULL,
  `time` datetime NOT NULL,
  `value` smallint(6) NOT NULL,
  PRIMARY KEY (`parameter`,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `current_values`
--

DROP TABLE IF EXISTS `current_values`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `current_values` (
  `parameter` char(5) NOT NULL,
  `time` datetime NOT NULL,
  `value` smallint(6) NOT NULL,
  PRIMARY KEY (`parameter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `energy`
--

DROP TABLE IF EXISTS `energy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `energy` (
  `date` date NOT NULL,
  `type` char(1) NOT NULL,
  `kwh` decimal(5,2) DEFAULT NULL,
  PRIMARY KEY (`date`,`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `holidays`
--

DROP TABLE IF EXISTS `holidays`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `holidays` (
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `reduction` smallint(6) NOT NULL,
  `minimum` smallint(6) NOT NULL,
  PRIMARY KEY (`start_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monitor`
--

DROP TABLE IF EXISTS `monitor`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `monitor` (
  `created` datetime NOT NULL,
  `parameter` char(5) NOT NULL,
  `value` smallint(6) NOT NULL,
  PRIMARY KEY (`created`,`parameter`),
  KEY `parameter` (`parameter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monitor_data`
--

DROP TABLE IF EXISTS `monitor_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `monitor_data` (
  `created_key` int(11) NOT NULL,
  `created_date` datetime NOT NULL,
  `converted` char(1) NOT NULL,
  `data` text DEFAULT NULL,
  PRIMARY KEY (`created_key`,`converted`),
  UNIQUE KEY `i_created` (`created_date`,`converted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
 PARTITION BY LIST  COLUMNS(`converted`)
(PARTITION `pUnconverted` VALUES IN ('N') ENGINE = InnoDB,
 PARTITION `pConverted` VALUES IN ('Y') ENGINE = InnoDB,
 PARTITION `pCompleted` VALUES IN ('Z') ENGINE = InnoDB);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `parameters`
--

DROP TABLE IF EXISTS `parameters`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `parameters` (
  `id` char(5) NOT NULL,
  `description` char(132) NOT NULL,
  `register` smallint(6) NOT NULL,
  `type` char(10) NOT NULL,
  `factor` float NOT NULL,
  `units` char(4) NOT NULL,
  `colour` char(15) NOT NULL,
  `monitor` char(1) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pending_values`
--

DROP TABLE IF EXISTS `pending_values`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `pending_values` (
  `created` char(12) NOT NULL,
  `parameter` char(5) NOT NULL,
  `value` int(11) NOT NULL,
  `repair_fails` smallint(6) NOT NULL DEFAULT 0,
  PRIMARY KEY (`created`,`parameter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `schedule`
--

DROP TABLE IF EXISTS `schedule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `schedule` (
  `season` char(7) NOT NULL,
  `days` char(75) NOT NULL,
  `zone` char(1) NOT NULL,
  `period` char(1) NOT NULL,
  `start` time NOT NULL,
  `end` time NOT NULL,
  `target` smallint(6) NOT NULL,
  PRIMARY KEY (`season`,`days`,`zone`,`period`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sessions`
--

DROP TABLE IF EXISTS `sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `sessions` (
  `user` char(10) NOT NULL,
  `session_id` char(36) NOT NULL,
  `message_id` char(36) NOT NULL,
  `last_message` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `data` blob NOT NULL,
  PRIMARY KEY (`user`,`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tariff_bands`
--

DROP TABLE IF EXISTS `tariff_bands`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tariff_bands` (
  `tariff_id` int(11) NOT NULL,
  `from_hour` smallint(6) NOT NULL,
  `price` int(11) NOT NULL,
  PRIMARY KEY (`tariff_id`,`from_hour`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tariffs`
--

DROP TABLE IF EXISTS `tariffs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tariffs` (
  `id` int(11) NOT NULL,
  `date_added` date NOT NULL,
  `current` char(1) DEFAULT 'N',
  `standing_charge` int(11) NOT NULL,
  `description` text NOT NULL,
  `exit_fee` smallint(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `uplift`
--

DROP TABLE IF EXISTS `uplift`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `uplift` (
  `date` date NOT NULL,
  `normal` double(7,4) NOT NULL,
  `alt` double(7,4) NOT NULL,
  `uplift` double(5,2) NOT NULL,
  PRIMARY KEY (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user` char(10) NOT NULL,
  `invalid_pwd` smallint(6) NOT NULL,
  `email` char(50) NOT NULL,
  `shash` char(90) NOT NULL,
  PRIMARY KEY (`user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-13 10:41:06
