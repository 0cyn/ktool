#include <Foundation/Foundation.h>

// clang testbin1.m -o testlib1.dylib -framework Foundation -dynamiclib

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

//int main(void) {
//    return 0;
//}
