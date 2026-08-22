// Boots MoeGUI via reflection — avoids module-boundary compile errors.
// javac sees no com.viper.moe reference; class resolved at runtime from the fat jar.
public class Launcher {
    public static void main(String[] args) throws Exception {
        Class<?> app = Class.forName("com.viper.moe.MoeApp");
        app.getMethod("main", String[].class).invoke(null, (Object) args);
    }
}
