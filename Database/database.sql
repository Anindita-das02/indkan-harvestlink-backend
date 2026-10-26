-- =====================================================
-- INDKAN HarvestLink - Enterprise B2B Export Engine
-- Complete Database Schema, Stored Procedures & Seed Data
-- File: Database/database.sql (inside Indkan_Backend/)
-- =====================================================

-- 1. DATABASE CREATION
CREATE DATABASE IF NOT EXISTS indkan_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE indkan_db;


-- =====================================================
-- 2. USERS TABLE (Admin & Buyer Profiles)
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    company_name VARCHAR(200) DEFAULT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(30) DEFAULT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'buyer', 'user') NOT NULL DEFAULT 'buyer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status_updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 3. CATEGORIES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 4. PRODUCTS TABLE (Agri Commodities Catalogue)
-- =====================================================

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    product_code VARCHAR(50) DEFAULT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(180) NOT NULL UNIQUE,
    short_description VARCHAR(300),
    description TEXT,
    origin_country VARCHAR(100) DEFAULT 'India',
    quality_grade VARCHAR(100) DEFAULT 'Grade A Sortex Cleaned',
    colour VARCHAR(100) DEFAULT NULL,
    storage_instructions TEXT DEFAULT NULL,
    minimum_order_quantity DECIMAL(12,3) DEFAULT 100.000,
    stock_quantity DECIMAL(12,2) DEFAULT 0.00,
    stock_unit VARCHAR(30) DEFAULT 'Metric Ton',
    moq_unit VARCHAR(20) NOT NULL DEFAULT 'kg',
    availability_status VARCHAR(50) NOT NULL DEFAULT 'in_stock',
    export_information TEXT DEFAULT NULL,
    image_data MEDIUMBLOB DEFAULT NULL,
    image_mime_type VARCHAR(100) DEFAULT NULL,
    image_filename VARCHAR(255) DEFAULT NULL,
    image_url VARCHAR(500) DEFAULT NULL,
    packaging_options JSON DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    KEY idx_products_category_active (category_id, is_active),
    KEY idx_products_active (is_active),
    CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 5. ENQUIRIES TABLE (Buyer RFQs & Live Tracking)
-- =====================================================

CREATE TABLE IF NOT EXISTS enquiries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    reference_id VARCHAR(50) DEFAULT NULL UNIQUE,
    secret_pin VARCHAR(50) DEFAULT NULL,
    user_id INT DEFAULT NULL,
    buyer_name VARCHAR(150) NOT NULL,
    company_name VARCHAR(200),
    buyer_type ENUM('wholesaler', 'distributor', 'retailer', 'other') NOT NULL DEFAULT 'other',
    email VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    country VARCHAR(100) DEFAULT NULL,
    destination_port VARCHAR(150) DEFAULT NULL,
    delivery_address TEXT DEFAULT NULL,
    tax_id VARCHAR(100) DEFAULT NULL,
    business_website VARCHAR(200) DEFAULT NULL,
    message TEXT,
    status ENUM('pending', 'contacted', 'completed', 'cancelled') NOT NULL DEFAULT 'pending',
    verification_status VARCHAR(50) DEFAULT 'pending',
    is_address_verified BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    status_updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_updated_by INT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    KEY fk_enquiries_status_updated_by (status_updated_by),
    KEY idx_enquiries_status_created (status, created_at),
    CONSTRAINT fk_enquiries_status_updated_by FOREIGN KEY (status_updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 6. ENQUIRY ITEMS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS enquiry_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    enquiry_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    unit VARCHAR(20) NOT NULL DEFAULT 'kg',
    packaging_requested VARCHAR(150),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    KEY fk_enquiry_items_product (product_id),
    KEY idx_enquiry_items_enquiry (enquiry_id),
    CONSTRAINT fk_enquiry_items_enquiry FOREIGN KEY (enquiry_id) REFERENCES enquiries(id) ON DELETE CASCADE,
    CONSTRAINT fk_enquiry_items_product FOREIGN KEY (product_id) REFERENCES products(id),
    CONSTRAINT chk_enquiry_items_quantity CHECK (quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 7. ENQUIRY STATUS AUDIT HISTORY TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS enquiry_status_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    enquiry_id BIGINT NOT NULL,
    old_status VARCHAR(50) DEFAULT NULL,
    new_status VARCHAR(50) NOT NULL,
    note TEXT DEFAULT NULL,
    changed_by VARCHAR(100) DEFAULT 'Admin',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    KEY enquiry_id (enquiry_id),
    CONSTRAINT fk_enquiry_history_enquiry FOREIGN KEY (enquiry_id) REFERENCES enquiries(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================
-- 8. STORED PROCEDURES
-- =====================================================

DROP PROCEDURE IF EXISTS sp_get_categories;
DROP PROCEDURE IF EXISTS sp_get_products;
DROP PROCEDURE IF EXISTS sp_get_product_by_id;
DROP PROCEDURE IF EXISTS sp_get_product_image;
DROP PROCEDURE IF EXISTS sp_save_enquiry;
DROP PROCEDURE IF EXISTS sp_save_enquiry_item;

DELIMITER $$

-- SP 1: GET ACTIVE CATEGORIES
CREATE PROCEDURE sp_get_categories()
BEGIN
    SELECT
        id,
        name,
        slug,
        description
    FROM categories
    WHERE is_active = TRUE
    ORDER BY name ASC;
END$$

-- SP 2: GET PRODUCTS (WITH OPTIONAL CATEGORY FILTER)
CREATE PROCEDURE sp_get_products(IN p_category_id INT)
BEGIN
    SELECT
        p.id,
        p.category_id,
        c.name AS category_name,
        c.slug AS category_slug,
        p.product_code,
        p.name,
        p.slug,
        p.short_description,
        p.description,
        p.origin_country,
        p.quality_grade,
        p.minimum_order_quantity,
        p.moq_unit,
        p.availability_status,
        p.packaging_options,
        p.image_url,
        p.image_mime_type,
        p.image_filename,
        p.created_at,
        p.updated_at
    FROM products p
    INNER JOIN categories c ON c.id = p.category_id
    WHERE p.is_active = TRUE
      AND c.is_active = TRUE
      AND (p_category_id IS NULL OR p.category_id = p_category_id)
    ORDER BY p.name ASC;
END$$

-- SP 3: GET PRODUCT DETAILS BY ID
CREATE PROCEDURE sp_get_product_by_id(IN p_product_id INT)
BEGIN
    SELECT
        p.id,
        p.category_id,
        c.name AS category_name,
        c.slug AS category_slug,
        p.product_code,
        p.name,
        p.slug,
        p.short_description,
        p.description,
        p.origin_country,
        p.quality_grade,
        p.colour,
        p.storage_instructions,
        p.minimum_order_quantity,
        p.moq_unit,
        p.availability_status,
        p.export_information,
        p.packaging_options,
        p.image_url,
        p.image_mime_type,
        p.image_filename,
        p.created_at,
        p.updated_at
    FROM products p
    INNER JOIN categories c ON c.id = p.category_id
    WHERE p.id = p_product_id
      AND p.is_active = TRUE
      AND c.is_active = TRUE
    LIMIT 1;
END$$

-- SP 4: GET PRODUCT IMAGE BLOB
CREATE PROCEDURE sp_get_product_image(IN p_product_id INT)
BEGIN
    SELECT
        p.image_data,
        p.image_mime_type,
        p.image_filename
    FROM products p
    INNER JOIN categories c ON c.id = p.category_id
    WHERE p.id = p_product_id
      AND p.is_active = TRUE
      AND c.is_active = TRUE
      AND p.image_data IS NOT NULL
    LIMIT 1;
END$$

-- SP 5: SAVE NEW ENQUIRY
CREATE PROCEDURE sp_save_enquiry(
    IN p_buyer_name VARCHAR(150),
    IN p_company_name VARCHAR(200),
    IN p_buyer_type VARCHAR(20),
    IN p_email VARCHAR(150),
    IN p_phone VARCHAR(30),
    IN p_country VARCHAR(100),
    IN p_message TEXT
)
BEGIN
    INSERT INTO enquiries (
        buyer_name,
        company_name,
        buyer_type,
        email,
        phone,
        country,
        message,
        status,
        verification_status,
        status_updated_at
    )
    VALUES (
        p_buyer_name,
        NULLIF(p_company_name, ''),
        p_buyer_type,
        p_email,
        p_phone,
        NULLIF(p_country, ''),
        p_message,
        'pending',
        'pending',
        CURRENT_TIMESTAMP
    );

    SELECT LAST_INSERT_ID() AS enquiry_id;
END$$

-- SP 6: SAVE ENQUIRY LINE ITEM
CREATE PROCEDURE sp_save_enquiry_item(
    IN p_enquiry_id BIGINT,
    IN p_product_id INT,
    IN p_quantity DECIMAL(12,3),
    IN p_unit VARCHAR(20),
    IN p_packaging_requested VARCHAR(150)
)
BEGIN
    IF p_quantity IS NULL OR p_quantity <= 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Quantity must be greater than zero';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM products p
        INNER JOIN categories c ON c.id = p.category_id
        WHERE p.id = p_product_id
          AND p.is_active = TRUE
          AND c.is_active = TRUE
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Product not found or inactive';
    END IF;

    INSERT INTO enquiry_items (
        enquiry_id,
        product_id,
        quantity,
        unit,
        packaging_requested
    )
    VALUES (
        p_enquiry_id,
        p_product_id,
        p_quantity,
        COALESCE(NULLIF(p_unit, ''), 'kg'),
        NULLIF(p_packaging_requested, '')
    );
END$$

DELIMITER ;


-- =====================================================
-- 9. SEED DATA (Local Testing & Evaluation Admin)
-- =====================================================

-- Default Super Admin (For local evaluation only. Password: admin123)
-- Change immediately in production using the Change Password feature
INSERT INTO users (id, name, email, password_hash, role, is_active)
VALUES (
    2,
    'INDKAN Super Admin',
    'admin@indkan.com',
    'scrypt:32768:8:1$KgJoRdWfaDIEzc4d$3dd92218c71258b7b2e4f54ff285f4a4847a0d0e3bf9bab0421c6e6006a529284a35b60e541cc0d19a839621274b683279e0b189bb4524a3a79385f73eff95a9',
    'admin',
    TRUE
)
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- Default Trade Categories
INSERT INTO categories (id, name, slug, description, is_active)
VALUES
    (1, 'Pulses & Lentils', 'pulses-lentils', 'Export-grade whole and split pulses, lentils, and grams sourced directly from certified agricultural hubs.', TRUE),
    (2, 'Premium Spices', 'premium-spices', 'High-potency whole and powdered spices harvested and graded according to international export standards.', TRUE)
ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description);

-- Initial Agri Commodities
INSERT INTO products (id, category_id, product_code, name, slug, short_description, description, origin_country, quality_grade, minimum_order_quantity, stock_quantity, stock_unit, moq_unit, availability_status, packaging_options, is_active)
VALUES
    (1, 1, 'RED-LEN-01', 'Red Lentils (Masoor Dal)', 'red-lentils', 'Quality red lentils for wholesale buyers and international export.', 'Export-grade cleaned and graded whole and split red lentils with high protein content and minimal moisture.', 'India', 'Grade A Sortex Cleaned', 100.000, 45.00, 'Metric Ton', 'kg', 'in_stock', '["25kg PP Bag", "50kg Jute Bag", "1MT Jumbo Bulk Bag"]', TRUE),
    (2, 1, 'GRN-MOO-02', 'Green Gram (Moong)', 'green-gram', 'Quality green gram for bulk supply and export markets.', 'Machine-cleaned, uniform green gram grains ideal for food processing, sprout cultivation, and wholesale distribution.', 'India', 'Sortex Clean 99.5% Purity', 100.000, 32.50, 'Metric Ton', 'kg', 'in_stock', '["25kg PP Bag", "50kg Woven Sack", "Bulk Liner"]', TRUE),
    (3, 2, 'TUR-CUR-03', 'Organic Turmeric (Curcumin 4%+)', 'turmeric', 'High-curcumin turmeric fingers and powder for wholesale enquiries.', 'A-Grade Alleppey/Salem turmeric fingers cured, sun-dried, and tested for high natural curcumin concentration.', 'India', 'Alleppey Turmeric Curcumin 4%+', 100.000, 0.00, 'Metric Ton', 'kg', 'out_of_stock', '["25kg Paper Craft Bags", "50kg Jute Bags"]', TRUE),
    (4, 2, 'BLK-PEP-04', 'Tellicherry Black Pepper', 'black-pepper', 'Black pepper bold grade for wholesale international buyers.', 'Premium grade whole black peppercorns from Malabar coast, sun-cured with pungent piperine profile.', 'India', 'Bold Garbled (550+ g/L)', 100.000, 8.20, 'Metric Ton', 'kg', 'low_stock', '["25kg Multiwall Paper Bag", "50kg PP Bag"]', TRUE),
    (8, 1, 'CHK-GAR-05', 'Kabuli Chickpeas (Garbanzo)', 'chickpeas', 'Selected chickpeas for retail, wholesale and food businesses.', 'Uniform size 8mm-10mm graded chickpeas with high yield and excellent canning/cooking qualities.', 'India', 'Grade A (75-80 Counts)', 100.000, 18.00, 'Metric Ton', 'kg', 'low_stock', '["25kg PP Bag", "50kg Jute Bag"]', TRUE),
    (9, 2, 'CHL-TEJ-06', 'Stemless Dry Red Chilli (S17 Teja)', 'red-chilli', 'Dried red chillies for wholesale and commercial requirements.', 'Vibrant red color, high SHU heat index, stemless sorted chillies suitable for spice grinders and oleoresin extraction.', 'India', 'Grade A Sun-Dried', 100.000, 60.00, 'Metric Ton', 'kg', 'in_stock', '["20kg Box Carton", "25kg Compressed Gunny Bale"]', TRUE)
ON DUPLICATE KEY UPDATE name = VALUES(name), product_code = VALUES(product_code);

-- =====================================================
-- END OF SCRIPT
-- =====================================================
