CREATE FUNCTION
    create_history_record()
    RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO a_history VALUES (NEW.*);
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO a_history (id) VALUES (OLD.id);
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO a_history VALUES (NEW.*);
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

sa.event.listen(
    RescuePlan.__translatable__['class'].__table__,
    'after_create',
    sa.schema.DDL(
CREATE TRIGGER a_create_version
AFTER INSERT OR UPDATE OR DELETE ON a
FOR EACH ROW
EXECUTE PROCEDURE create_version();
