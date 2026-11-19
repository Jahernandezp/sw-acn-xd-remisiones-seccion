-- Actualización de fk_department en ItemRemision
-- Remisiones del 2026-11-18 (hora CDMX)
-- Generado: 2026-11-19 11:50:00
-- Items a actualizar: 3
-- Items sin departamento encontrado: 1

START TRANSACTION;

UPDATE ItemRemision SET fk_department = '550' WHERE IDItemRemision = 210638285 AND (fk_department = 0 OR fk_department IS NULL); -- SKU 1192530047
UPDATE ItemRemision SET fk_department = '357' WHERE IDItemRemision = 210665453 AND (fk_department = 0 OR fk_department IS NULL); -- SKU 1201756495
UPDATE ItemRemision SET fk_department = '555' WHERE IDItemRemision = 210679533 AND (fk_department = 0 OR fk_department IS NULL); -- SKU 1201564472

-- Revisa el resultado y ejecuta COMMIT; para confirmar o ROLLBACK; para deshacer.
-- COMMIT;

-- Items sin departamento en ningún otro registro con el mismo SKU (no se actualizan):
--   IDItemRemision 210650873, SKU 1201616936
