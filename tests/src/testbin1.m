#include <Foundation/Foundation.h>

// clang testbin1.m -o testbin1 -framework Foundation

@interface TestClassOne : NSObject

@property CGRect testPropertyOne;
@property (atomic, readonly) BOOL testPropertyTwo;

-(NSUInteger)testInstanceMethodOne;
+(BOOL)testClassMethodOne;

@end

@implementation TestClassOne

- (NSUInteger)testInstanceMethodOne
{
    return 0;
}

+ (BOOL)testClassMethodOne
{
    return YES;
}

@end

int main(void) {
    return 0;
}
