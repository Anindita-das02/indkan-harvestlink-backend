
-- =====================================================
-- INDKAN HarvestLink
-- Complete Database and Stored Procedures
-- File: backend/database/database.sql
-- =====================================================


-- 1. CREATE DATABASE
CREATE DATABASE IF NOT EXISTS indkan_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE indkan_db;


-- =====================================================
-- 2. USERS TABLE (Admin accounts only)
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin') NOT NULL DEFAULT 'admin',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status_updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);


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
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);


-- =====================================================
-- 4. PRODUCTS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(180) NOT NULL UNIQUE,
    short_description VARCHAR(300),
    description TEXT,
    image_data MEDIUMBLOB,
    image_mime_type VARCHAR(100),
    image_filename VARCHAR(255),
    packaging_options JSON,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (category_id)
        REFERENCES categories(id)
);


-- =====================================================
-- 5. ENQUIRIES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS enquiries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    buyer_name VARCHAR(150) NOT NULL,
    company_name VARCHAR(200),
    buyer_type ENUM(
        'wholesaler',
        'distributor',
        'retailer',
        'other'
    ) NOT NULL DEFAULT 'other',
    email VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    message TEXT,
    status ENUM(
        'pending',
        'contacted',
        'completed',
        'cancelled'
    ) NOT NULL DEFAULT 'pending',
    admin_notes TEXT,
    status_updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_updated_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (status_updated_by)
        REFERENCES users(id)
        ON DELETE SET NULL
);


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

    FOREIGN KEY (enquiry_id)
        REFERENCES enquiries(id)
        ON DELETE CASCADE,

    FOREIGN KEY (product_id)
        REFERENCES products(id),

    CHECK (quantity > 0)
);


-- =====================================================
-- 7. REMOVE OLD STORED PROCEDURES IF THEY EXIST
-- =====================================================

DROP PROCEDURE IF EXISTS sp_get_categories;
DROP PROCEDURE IF EXISTS sp_get_products;
DROP PROCEDURE IF EXISTS sp_get_product_by_id;
DROP PROCEDURE IF EXISTS sp_get_product_image;
DROP PROCEDURE IF EXISTS sp_save_enquiry;
DROP PROCEDURE IF EXISTS sp_save_enquiry_item;

DELIMITER $$


-- =====================================================
-- SP 1: GET ALL ACTIVE CATEGORIES
-- =====================================================

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


-- =====================================================
-- SP 2: GET ACTIVE PRODUCTS
-- Pass NULL to get all products.
-- Pass category ID to filter products.
-- =====================================================

CREATE PROCEDURE sp_get_products(
    IN p_category_id INT
)
BEGIN
    SELECT
        p.id,
        p.category_id,
        c.name AS category_name,
        p.name,
        p.slug,
        p.short_description,
        p.description,
        p.packaging_options,
        p.image_mime_type,
        p.image_filename,
        p.created_at,
        p.updated_at
    FROM products p
    INNER JOIN categories c
        ON c.id = p.category_id
    WHERE p.is_active = TRUE
      AND c.is_active = TRUE
      AND (
          p_category_id IS NULL
          OR p.category_id = p_category_id
      )
    ORDER BY p.name ASC;
END$$


-- =====================================================
-- SP 3: GET ONE PRODUCT BY ID
-- =====================================================

CREATE PROCEDURE sp_get_product_by_id(
    IN p_product_id INT
)
BEGIN
    SELECT
        p.id,
        p.category_id,
        c.name AS category_name,
        p.name,
        p.slug,
        p.short_description,
        p.description,
        p.packaging_options,
        p.image_mime_type,
        p.image_filename,
        p.created_at,
        p.updated_at
    FROM products p
    INNER JOIN categories c
        ON c.id = p.category_id
    WHERE p.id = p_product_id
      AND p.is_active = TRUE
      AND c.is_active = TRUE
    LIMIT 1;
END$$


-- =====================================================
-- SP 4: GET PRODUCT IMAGE
-- =====================================================

CREATE PROCEDURE sp_get_product_image(
    IN p_product_id INT
)
BEGIN
    SELECT
        image_data,
        image_mime_type,
        image_filename
    FROM products
    WHERE id = p_product_id
      AND is_active = TRUE
      AND image_data IS NOT NULL
    LIMIT 1;
END$$


-- =====================================================
-- SP 5: SAVE BUYER ENQUIRY
-- Returns the newly created enquiry ID.
-- =====================================================

CREATE PROCEDURE sp_save_enquiry(
    IN p_buyer_name VARCHAR(150),
    IN p_company_name VARCHAR(200),
    IN p_buyer_type VARCHAR(20),
    IN p_email VARCHAR(150),
    IN p_phone VARCHAR(30),
    IN p_message TEXT
)
BEGIN
    INSERT INTO enquiries (
        buyer_name,
        company_name,
        buyer_type,
        email,
        phone,
        message,
        status,
        status_updated_at
    )
    VALUES (
        p_buyer_name,
        NULLIF(p_company_name, ''),
        p_buyer_type,
        p_email,
        p_phone,
        p_message,
        'pending',
        CURRENT_TIMESTAMP
    );

    SELECT LAST_INSERT_ID() AS enquiry_id;
END$$


-- =====================================================
-- SP 6: SAVE ENQUIRY PRODUCT ITEM
-- Call once for each selected product.
-- =====================================================

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
            SET MESSAGE_TEXT =
                'Quantity must be greater than zero';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM products p
        INNER JOIN categories c
            ON c.id = p.category_id
        WHERE p.id = p_product_id
          AND p.is_active = TRUE
          AND c.is_active = TRUE
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT =
                'Product not found or inactive';
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
-- END OF SCRIPT
-- =====================================================
