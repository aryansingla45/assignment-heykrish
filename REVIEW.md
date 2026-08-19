# Review of Agency Shelf Analysis

## Overview

We reviewed the agency's SQL scripts and their reported numbers, including the claim that **Britannia has 22% of the biscuit shelf**.

We tested the same logic using live data from the Open Food Facts API, covering **1,534 products in India**. We found five major issues that can significantly affect the results.

Below is a simple summary of what we found and how we fixed it.

---

## 1. Duplicate Products

### What was wrong

The agency's script inserts every product directly into the database.

Because Open Food Facts is regularly updated, running the script again can insert the same product multiple times. This increases the product count even though no new products were actually added.

In our test, running the same import twice resulted in **double the number of product rows**.

### What we changed

We use the product **barcode as a unique identifier** and perform an upsert.

This means:

* Existing products are updated.
* New products are added.
* Running the pipeline multiple times does not create duplicates.

---

## 2. Products Can Belong to Multiple Categories

### What was wrong

The agency uses a single `category` field for each product.

However, a product can belong to more than one category. For example, a product can be tagged as both **biscuits** and **cookies**.

In our data, **371 products (24.2%)** had multiple relevant category tags.

With a single category field, these products can either be assigned incorrectly or duplicated.

### What we changed

We created a separate `product_categories` table.

This allows one product to belong to multiple categories while still keeping the product itself unique.

This also means we can count:

`DISTINCT barcode`

for each category and avoid double counting.

---

## 3. Incorrect Market Share Calculation

### What was wrong

The agency reported that Britannia has **22% of the biscuit shelf**.

Using the corrected data, we found:

* **800** total biscuit products
* **144** Britannia biscuit products
* Actual share: **18.0%**

The difference came from using an incorrect denominator in the agency's calculation.

### What we changed

Our calculations only compare brands against products within the same category.

For example:

**Britannia biscuit products ÷ total biscuit products**

This prevents products from other categories from affecting the market share calculation.

---

## 4. Brand Names Are Inconsistent

### What was wrong

Brand names in Open Food Facts are entered by users, so the same brand can appear in different formats.

For example:

* `Britannia`
* `BRITANNIA`
* `britannia`
* `Britannia Industries`

Our raw data contained **38 different variations of major brand names**.

If these are treated as separate brands, the actual market share gets split across multiple entries.

### What we changed

We added brand normalization that:

* Converts names to lowercase
* Removes unnecessary spaces
* Handles multiple brand values consistently

We also keep the original `brand_raw` value so the original data is not lost.

---

## 5. Sugar Data Has Missing Values and Invalid Entries

### What was wrong

The agency provided an average sugar value without clearly accounting for data quality.

We found two major issues.

**Invalid values:**
5 products reported more than **100g of sugar per 100g**, including values such as 250g/100g. These are clearly invalid data entries and can distort the average.

**Missing values:**
**613 out of 1,534 products (45.8%)** do not have sugar information.

This means any reported average only represents the products where sugar data is available.

### What we changed

We exclude impossible sugar values above 100g/100g from the calculation.

We also report **data coverage** alongside the average.

This makes it clear how much of the shelf the calculation actually represents.

---

## Conclusion

The agency's analysis has several data and calculation issues that can affect the reported shelf size, brand shares, and nutritional analysis.

We addressed these issues by:

* Preventing duplicate products
* Supporting multiple categories per product
* Using the correct denominator for market share
* Normalizing brand names
* Removing invalid nutritional values
* Reporting missing-data coverage

The resulting pipeline is more reliable, repeatable, and easier to verify. Most importantly, the numbers can now be traced back to the underlying product data and the exact calculation used.
