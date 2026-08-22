module com.viper.moe {
    requires javafx.controls;
    requires javafx.fxml;
    requires javafx.graphics;
    requires java.sql;
    requires java.desktop;
    requires com.fasterxml.jackson.databind;

    opens com.viper.moe to javafx.fxml;
    exports com.viper.moe;
}
